
# Network Resource Allocation and Reservation System

## 1. Project Overview

The **Network Resource Allocation and Reservation System** is a TCP-based client-server application designed to manage and allocate network bandwidth among multiple clients.

The system allows clients to request bandwidth reservations between network hosts for a specified duration. A centralized server processes these requests, checks resource availability, detects reservation conflicts, and accepts or rejects requests based on the available network capacity.

The project integrates **Software Defined Networking (SDN)** using the POX controller and Mininet to demonstrate centralized network management and policy enforcement.

## 2. Objectives

- Implement a TCP-based client-server communication system.
- Support multiple clients requesting network resources simultaneously.
- Maintain information about available and allocated bandwidth.
- Detect bandwidth allocation conflicts.
- Accept or reject reservation requests based on available capacity.
- Implement reservation expiration.
- Integrate SDN policies through the POX controller.
- Monitor network utilization through a statistics interface.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python 3 | Application development |
| TCP Sockets | Client-server communication |
| Mininet | Network emulation |
| POX Controller | SDN control and policy management |
| OpenFlow 1.0 | Communication between switches and controller |
| Linux / Ubuntu | Execution environment |
| JSON | Request and response data exchange |

## 4. System Architecture

The system follows a centralized client-server architecture.

- **Centralized Server (h1):** Receives requests, maintains bandwidth information, validates reservations, and manages resource allocation.
- **Clients (h2, h3, h4):** Send bandwidth reservation requests to the centralized server.
- **POX Controller:** Handles SDN-related policy enforcement.
- **Mininet:** Emulates the network topology and connected hosts.

### Architecture Flow

1. A client sends a bandwidth reservation request to the server.
2. The server receives and processes the request.
3. The requested bandwidth is compared against available capacity.
4. The request is accepted or rejected.
5. If accepted, the reservation is recorded and the corresponding SDN policy is installed.
6. The reservation automatically expires after its specified duration.
7. Clients can request statistics to monitor resource utilization.

## 5. Network Topology

The project uses Mininet to emulate a network consisting of multiple hosts connected through a software switch.

| Host | Role |
|---|---|
| h1 | Centralized Reservation Server |
| h2 | Client 1 |
| h3 | Client 2 |
| h4 | Client 3 |

The server runs on h1, while h2, h3, and h4 communicate with it to request bandwidth reservations.

## 6. Project Structure

```text
Network-Resource-Allocation/
│
├── server.py
├── client.py
├── topology.py
├── reservation_controller.py
│
└── README.md
```

## 7. Features

### 7.1 Bandwidth Reservation
Clients can request a specific amount of bandwidth for a specified duration.

### 7.2 Multiple Client Support
Multiple clients can connect to the centralized server and submit reservation requests.

### 7.3 Resource Management
The server maintains:
- Total network capacity
- Allocated bandwidth
- Available bandwidth
- Active reservations

### 7.4 Reservation Validation
The server checks whether sufficient bandwidth is available before accepting a request.

### 7.5 Reservation Expiration
Reservations are automatically expired after their specified duration, making the allocated bandwidth available again.

### 7.6 SDN Policy Integration
The POX controller is used to manage network policies based on accepted reservations.

### 7.7 Statistics Monitoring
Clients can view:
- Number of connected clients
- Total reservation requests
- Accepted requests
- Rejected requests
- Expired reservations
- Total bandwidth capacity
- Allocated bandwidth
- Available bandwidth
- Active reservations

## 8. Installation and Setup

### Prerequisites

- Ubuntu Linux
- Python 3
- Mininet
- POX Controller
- Open vSwitch

### Step 1: Clone the Repository

```bash
git clone https://github.com/USERNAME/REPOSITORY.git
cd REPOSITORY
```

### Step 2: Start the POX Controller

Open a terminal and navigate to the POX directory.

```bash
./pox.py openflow.of_01 --port=6633 reservation_controller
```

### Step 3: Start the Mininet Topology

Open another terminal and navigate to the project directory.

```bash
sudo python3 topology.py
```

### Step 4: Start the Reservation Server

Run the server inside host h1 using the Mininet host namespace.

```bash
sudo mnexec -a $(pgrep -f mininet:h1 | head -1) python3 ~/network-reservation/server.py
```

### Step 5: Start Clients

Run clients inside h2, h3, and h4 using separate terminals.

Example for h2:

```bash
sudo mnexec -a $(pgrep -f mininet:h2 | head -1) python3 ~/network-reservation/client.py
```

Repeat for h3 and h4.

**Note:** Update the project directory paths according to your local setup.

## 9. Client Operations

The client interface provides the following options:

```text
1. Make Reservation
2. View Statistics
3. Quit
```

### Example Reservation Request

```json
{
    "source": "h1",
    "destination": "h3",
    "bandwidth_mbps": 60,
    "duration_seconds": 20
}
```

### Example Accepted Response

```json
{
    "status": "accepted",
    "reservation_id": "R123456",
    "source": "h1",
    "destination": "h3",
    "bandwidth_mbps": 60,
    "duration_seconds": 20,
    "sdn_policy": "installed"
}
```

### Example Statistics

```json
{
    "status": "ok",
    "statistics": {
        "connected_clients": 1,
        "total_requests": 2,
        "accepted": 2,
        "rejected": 0,
        "expired": 1,
        "capacity_mbps": 100,
        "allocated_mbps": 70,
        "available_mbps": 30,
        "active_reservations": 1
    }
}
```

## 10. Expected Outcome

The system demonstrates how centralized network resource allocation can be implemented using TCP communication and SDN.

It provides controlled bandwidth allocation, concurrent client handling, reservation management, automatic expiration, and network statistics monitoring.

## 11. Future Enhancements

- Dynamic bandwidth allocation.
- Priority-based reservation scheduling.
- Web-based monitoring dashboard.
- Advanced traffic management.
- Improved fault tolerance.
- Detailed network performance analysis.

## 12. Conclusion

The Network Resource Allocation and Reservation System demonstrates the practical implementation of network resource management using socket programming and Software Defined Networking.

By combining TCP-based client-server communication with Mininet and the POX controller, the project provides a framework for managing bandwidth reservations and monitoring network resource utilization.

---

**Course:** Computer Networks  
**Project:** Network Resource Allocation and Reservation System  
**Implementation Language:** Python
