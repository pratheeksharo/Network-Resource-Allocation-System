"""
POX application for the fixed four-host topology.
Run with: ./pox.py forwarding.l2_learning reservation_controller
Policy listener binds to the Mininet switch's internal IP 10.0.0.254:9999.
"""
import json, socket, threading
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr
from pox.lib.packet.ethernet import ethernet

log = core.getLogger()
switches = {}
installed = {}
lock = threading.RLock()

HOSTS = {
    "h1": ("10.0.0.1", 1), "h2": ("10.0.0.2", 2),
    "h3": ("10.0.0.3", 3), "h4": ("10.0.0.4", 4)
}

def handle_connection_up(event):
    with lock:
        switches[event.dpid] = event.connection
    # ARP must work for host discovery and IP communication.
    arp = of.ofp_flow_mod()
    arp.match.dl_type = ethernet.ARP_TYPE
    arp.priority = 100
    arp.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
    event.connection.send(arp)
    # Low-priority fallback. Reservation-specific rules take precedence.
    default = of.ofp_flow_mod()
    default.priority = 1
    default.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
    event.connection.send(default)
    log.info("Switch connected: dpid=%s", event.dpid)

def apply_policy(request):
    source, destination = request.get("source"), request.get("destination")
    if source not in HOSTS or destination not in HOSTS or source == destination:
        return {"status": "error", "detail": "Invalid source/destination"}
    with lock:
        connections = list(switches.values())
    if not connections:
        return {"status": "error", "detail": "No OpenFlow switch connected"}

    rid = request.get("reservation_id")
    operation = request.get("operation", "install")
    src_ip, _ = HOSTS[source]
    dst_ip, dst_port = HOSTS[destination]

    for connection in connections:
        match = of.ofp_match()
        match.dl_type = ethernet.IP_TYPE
        match.nw_src = IPAddr(src_ip)
        match.nw_dst = IPAddr(dst_ip)
        if operation == "remove":
            flow = of.ofp_flow_mod(command=of.OFPFC_DELETE)
            flow.match = match
            flow.priority = 200
            connection.send(flow)
        else:
            flow = of.ofp_flow_mod()
            flow.match = match
            flow.priority = 200
            flow.idle_timeout = 0
            flow.hard_timeout = int(request.get("duration_seconds", 0))
            flow.actions.append(of.ofp_action_output(port=dst_port))
            connection.send(flow)

    with lock:
        if operation == "remove":
            installed.pop(rid, None)
        else:
            installed[rid] = request
    log.info("%s SDN forwarding policy for %s -> %s reservation=%s",
             operation, source, destination, rid)
    return {"status": "removed" if operation == "remove" else "installed"}

def policy_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", 9999))
        server.listen(20)
        log.info("Reservation policy listener on 10.0.0.254:9999")
        while True:
            conn, addr = server.accept()
            with conn:
                try:
                    line = conn.makefile("r").readline()
                    request = json.loads(line)
                    result = {}
                    done = threading.Event()
                    def apply():
                        try:
                            result.update(apply_policy(request))
                        except Exception as exc:
                            result.update({"status": "error", "detail": str(exc)})
                        finally:
                            done.set()
                    core.callLater(apply)
                    if done.wait(5):
                        response = result
                    else:
                        response = {"status": "error", "detail": "Controller operation timed out"}
                    conn.sendall((json.dumps(response) + "\n").encode())
                except Exception as exc:
                    log.exception("Policy request failed")
                    try:
                        conn.sendall((json.dumps({"status": "error", "detail": str(exc)}) + "\n").encode())
                    except Exception:
                        pass

def launch():
    core.openflow.addListenerByName("ConnectionUp", handle_connection_up)
    threading.Thread(target=policy_listener, daemon=True).start()
    log.info("Network Resource Reservation Controller started")