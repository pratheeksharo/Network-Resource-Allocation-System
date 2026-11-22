#!/usr/bin/env python3
"""Interactive TCP reservation client. Run inside h2, h3, or h4."""

import json
import socket
import sys
import subprocess

SERVER_HOST = "10.0.0.1"
SERVER_PORT = 9000

DESTINATION_HOST = "h1"

def get_client_host():
    result = subprocess.run(
        ["hostname", "-I"],
        capture_output=True,
        text=True
    )

    ip = result.stdout.strip().split()[0]

    host_map = {
        "10.0.0.2": "h2",
        "10.0.0.3": "h3",
        "10.0.0.4": "h4"
    }

    return host_map.get(ip, "unknown")


def main():
    if len(sys.argv) > 1:
        server_host = sys.argv[1]
    else:
        server_host = SERVER_HOST

    source_host = get_client_host()

    if source_host not in ("h2", "h3", "h4"):
        print("Error: Run this client inside h2, h3, or h4.")
        return

    with socket.create_connection(
        (server_host, SERVER_PORT), timeout=8
    ) as sock:

        reader = sock.makefile("r")

        print(f"Connected to reservation server at {server_host}:{SERVER_PORT}")
        print(f"Client host: {source_host}")
        print(f"Destination host: {DESTINATION_HOST}")

        while True:
            print("\n1. Make reservation  2. View statistics  3. Quit")

            choice = input("Choice: ").strip()

            if choice == "3":
                break

            if choice == "2":
                request = {"command": "stats"}

            elif choice == "1":

                print(f"\nReservation: {source_host} -> {DESTINATION_HOST}")

                try:
                    request = {
                        "source": source_host,
                        "destination": DESTINATION_HOST,
                        "bandwidth_mbps": int(input("Bandwidth (Mbps): ")),
                        "duration_seconds": int(input("Duration (seconds): "))
                    }

                except ValueError:
                    print("Enter valid integer values.")
                    continue

            else:
                print("Invalid choice")
                continue

            sock.sendall((json.dumps(request) + "\n").encode())

            response = reader.readline()

            if not response:
                print("Server disconnected")
                break

            print(json.dumps(json.loads(response), indent=2))


if __name__ == "__main__":
    main()