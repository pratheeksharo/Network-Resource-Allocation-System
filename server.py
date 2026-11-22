#!/usr/bin/env python3
"""
Centralized TCP Network Resource Reservation Server with traffic shaping.

Run this server inside Mininet host h1.
All clients h2, h3 and h4 share one 100 Mbps reservation pool.

Traffic enforcement:
- Each client host's egress interface is shaped to the sum of its active
  reservations to h1.
- A host with no active reservation is limited to a small control allowance.
- The sum of accepted reservations across h2, h3 and h4 cannot exceed 100 Mbps.

This is rate limiting (a maximum rate), not a guaranteed minimum bandwidth.
"""
import json
import socket
import threading
import time
import subprocess

SERVER_HOST = "10.0.0.1"
SERVER_PORT = 9000

CONTROLLER_HOST = "10.0.0.254"
CONTROLLER_PORT = 9999

TOTAL_CAPACITY_MBPS = 100
VALID_CLIENTS = {"h2", "h3", "h4"}
CLIENT_IP_TO_HOST = {
    "10.0.0.2": "h2",
    "10.0.0.3": "h3",
    "10.0.0.4": "h4",
}

# Hosts with no active reservation retain a tiny rate for control/test traffic.
IDLE_RATE_KBIT = 100

reservations = {}
connected_clients = set()
stats = {
    "total_requests": 0,
    "accepted_requests": 0,
    "rejected_requests": 0,
    "expired_reservations": 0,
}
lock = threading.RLock()


def current_time():
    return time.time()


def send_controller_policy(reservation, operation):
    message = dict(reservation)
    message["operation"] = operation

    with socket.create_connection(
        (CONTROLLER_HOST, CONTROLLER_PORT), timeout=5
    ) as controller_socket:
        controller_socket.settimeout(5)
        controller_socket.sendall(
            (json.dumps(message) + "\n").encode("utf-8")
        )
        reader = controller_socket.makefile("r", encoding="utf-8")
        response_line = reader.readline()

    if not response_line:
        return {"status": "error", "detail": "Controller returned an empty response"}

    try:
        return json.loads(response_line)
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "detail": f"Invalid JSON response from controller: {exc}",
            "raw_response": response_line,
        }


def allocated_bandwidth_locked():
    return sum(item["bandwidth_mbps"] for item in reservations.values())


def host_allocations_locked():
    totals = {host: 0 for host in VALID_CLIENTS}
    for item in reservations.values():
        totals[item["source"]] += item["bandwidth_mbps"]
    return totals


def apply_host_shaping(host, bandwidth_mbps):
    """
    Apply a Linux TBF egress rate limit to the Mininet host's interface.

    The server runs in h1, but mnexec enters the target host's network
    namespace before configuring its hX-eth0 interface.
    """
    if host not in VALID_CLIENTS:
        raise ValueError(f"Invalid shaping host: {host}")

    if bandwidth_mbps > 0:
        rate = f"{bandwidth_mbps}mbit"
    else:
        rate = f"{IDLE_RATE_KBIT}kbit"

    command = (
        f"pid=$(pgrep -f 'mininet:{host}' | head -n 1); "
        f"test -n \"$pid\" || exit 10; "
        f"mnexec -a \"$pid\" tc qdisc replace dev {host}-eth0 "
        f"root tbf rate {rate} burst 32kbit latency 400ms"
    )

    result = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        timeout=8,
    )

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"Could not shape {host} to {rate}. "
            f"Check Mininet host process, interface and tc. {detail}"
        )

    print(f"[QOS] {host}-eth0 egress rate set to {rate}")


def update_all_host_shaping_locked():
    """Recalculate and apply shaping for h2, h3 and h4. Caller holds lock."""
    totals = host_allocations_locked()
    for host in sorted(VALID_CLIENTS):
        apply_host_shaping(host, totals[host])


def make_statistics():
    with lock:
        allocated = allocated_bandwidth_locked()
        per_host = host_allocations_locked()
        return {
            "connected_clients": len(connected_clients),
            "total_requests": stats["total_requests"],
            "accepted_requests": stats["accepted_requests"],
            "rejected_requests": stats["rejected_requests"],
            "expired_reservations": stats["expired_reservations"],
            "total_capacity_mbps": TOTAL_CAPACITY_MBPS,
            "allocated_bandwidth_mbps": allocated,
            "available_bandwidth_mbps": TOTAL_CAPACITY_MBPS - allocated,
            "active_reservations": len(reservations),
            "h2_allocated_mbps": per_host["h2"],
            "h3_allocated_mbps": per_host["h3"],
            "h4_allocated_mbps": per_host["h4"],
            "traffic_shaping": "Linux tc TBF enabled",
        }


def print_statistics():
    data = make_statistics()
    print("\n========== CENTRAL RESERVATION SERVER STATISTICS ==========")
    for key, value in data.items():
        print(f"{key.replace('_', ' ').title():32}: {value}")
    print("===========================================================\n")


def reject(reason, **extra):
    result = {"status": "rejected", "reason": reason}
    result.update(extra)
    return result


def handle_reservation(request, client_id):
    required = {"source", "destination", "bandwidth_mbps", "duration_seconds"}
    missing = required - set(request)
    if missing:
        return {"status": "error", "reason": f"Missing fields: {', '.join(sorted(missing))}"}

    source = str(request["source"]).strip()
    destination = str(request["destination"]).strip()

    try:
        bandwidth = int(request["bandwidth_mbps"])
        duration = int(request["duration_seconds"])
    except (TypeError, ValueError):
        return {"status": "error", "reason": "Bandwidth and duration must be integers"}

    client_ip = client_id.split(":", 1)[0]
    actual_client_host = CLIENT_IP_TO_HOST.get(client_ip)

    if actual_client_host not in VALID_CLIENTS:
        with lock:
            stats["total_requests"] += 1
            stats["rejected_requests"] += 1
        return reject("Client IP is not a registered Mininet client", client_ip=client_ip)

    if source != actual_client_host:
        with lock:
            stats["total_requests"] += 1
            stats["rejected_requests"] += 1
        return reject(
            "Source host must match the connected client",
            connected_client=actual_client_host,
            requested_source=source,
        )

    if destination != "h1":
        with lock:
            stats["total_requests"] += 1
            stats["rejected_requests"] += 1
        return reject("Destination must be h1")

    if bandwidth <= 0 or duration <= 0:
        with lock:
            stats["total_requests"] += 1
            stats["rejected_requests"] += 1
        return reject("Bandwidth and duration must be positive")

    if bandwidth > TOTAL_CAPACITY_MBPS:
        with lock:
            stats["total_requests"] += 1
            stats["rejected_requests"] += 1
        return reject(
            "Requested bandwidth exceeds total network capacity",
            capacity_mbps=TOTAL_CAPACITY_MBPS,
        )

    reservation_id = f"R{int(current_time() * 1000)}-{threading.get_ident()}"
    reservation = {
        "reservation_id": reservation_id,
        "source": source,
        "destination": destination,
        "bandwidth_mbps": bandwidth,
        "duration_seconds": duration,
        "client_id": client_id,
        "created_at": current_time(),
        "expires_at": current_time() + duration,
    }

    with lock:
        stats["total_requests"] += 1
        allocated = allocated_bandwidth_locked()
        available = TOTAL_CAPACITY_MBPS - allocated

        if bandwidth > available:
            stats["rejected_requests"] += 1
            return reject(
                "Insufficient shared network capacity",
                requested_mbps=bandwidth,
                available_mbps=available,
            )

        # Reserve capacity atomically before waiting on the controller.
        reservations[reservation_id] = reservation

        try:
            controller_result = send_controller_policy(reservation, "install")
        except (OSError, TimeoutError) as exc:
            controller_result = {"status": "error", "detail": str(exc)}

        if controller_result.get("status") != "installed":
            reservations.pop(reservation_id, None)
            stats["rejected_requests"] += 1
            return {
                "status": "rejected",
                "reason": "SDN controller could not install the policy",
                "controller_detail": controller_result.get("detail", "Unknown controller error"),
            }

        try:
            update_all_host_shaping_locked()
        except Exception as exc:
            # Roll back server state and controller rule if traffic shaping fails.
            reservations.pop(reservation_id, None)
            try:
                send_controller_policy(reservation, "remove")
                update_all_host_shaping_locked()
            except Exception as rollback_exc:
                print(f"[ROLLBACK WARNING] {rollback_exc}")
            stats["rejected_requests"] += 1
            return {
                "status": "rejected",
                "reason": "Could not apply Linux traffic shaping",
                "shaping_detail": str(exc),
            }

        stats["accepted_requests"] += 1

    return {
        "status": "accepted",
        **reservation,
        "sdn_policy": "installed",
        "traffic_shaping": "applied",
    }


def expire_reservations_worker():
    while True:
        time.sleep(1)
        expired_items = []

        with lock:
            now = current_time()
            for reservation_id, item in list(reservations.items()):
                if item["expires_at"] <= now:
                    expired_items.append(item)
                    del reservations[reservation_id]
                    stats["expired_reservations"] += 1

            if expired_items:
                try:
                    update_all_host_shaping_locked()
                except Exception as exc:
                    print(f"[QOS EXPIRY WARNING] Could not update traffic shaping: {exc}")

        for item in expired_items:
            try:
                result = send_controller_policy(item, "remove")
                print(
                    f"[EXPIRY] {item['reservation_id']} released; "
                    f"controller={result.get('status')}"
                )
            except (OSError, TimeoutError) as exc:
                print(f"[EXPIRY WARNING] Could not contact POX to remove rule: {exc}")

        if expired_items:
            print_statistics()


def handle_client(connection, address):
    client_id = f"{address[0]}:{address[1]}"
    with lock:
        connected_clients.add(client_id)

    print(f"[CLIENT CONNECTED] {client_id}")
    print_statistics()

    try:
        reader = connection.makefile("r", encoding="utf-8")
        for line in reader:
            if not line.strip():
                continue

            try:
                request = json.loads(line)
                if request.get("command") == "stats":
                    response = {"status": "ok", "statistics": make_statistics()}
                else:
                    response = handle_reservation(request, client_id)

                connection.sendall(
                    (json.dumps(response) + "\n").encode("utf-8")
                )
                print(f"[CLIENT REQUEST] {client_id}: {response}")
                print_statistics()

            except json.JSONDecodeError:
                response = {"status": "error", "reason": "Request must be valid JSON"}
                connection.sendall(
                    (json.dumps(response) + "\n").encode("utf-8")
                )
            except Exception as exc:
                response = {"status": "error", "reason": str(exc)}
                connection.sendall(
                    (json.dumps(response) + "\n").encode("utf-8")
                )
                print(f"[ERROR] Request from {client_id}: {exc}")

    except (ConnectionError, OSError) as exc:
        print(f"[CLIENT CONNECTION ERROR] {client_id}: {exc}")
    finally:
        with lock:
            connected_clients.discard(client_id)
        connection.close()
        print(f"[CLIENT DISCONNECTED] {client_id}")
        print_statistics()


def main():
    # Set all client hosts to the idle/control rate when the server starts.
    # This prevents unreserved clients from sending unrestricted data traffic.
    for host in sorted(VALID_CLIENTS):
        try:
            apply_host_shaping(host, 0)
        except Exception as exc:
            print(f"[STARTUP QOS WARNING] {host}: {exc}")

    threading.Thread(
        target=expire_reservations_worker,
        name="reservation-expiry",
        daemon=True,
    ).start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((SERVER_HOST, SERVER_PORT))
        server_socket.listen(20)

        print("Centralized Network Resource Reservation Server")
        print(f"Listening on {SERVER_HOST}:{SERVER_PORT}")
        print(f"Shared network capacity: {TOTAL_CAPACITY_MBPS} Mbps")
        print("Linux tc traffic shaping: enabled")
        print("Waiting for multiple TCP clients...")

        while True:
            connection, address = server_socket.accept()
            worker = threading.Thread(
                target=handle_client,
                args=(connection, address),
                daemon=True,
            )
            worker.start()


if __name__ == "__main__":
    main()