#!/usr/bin/env python3
"""Fixed topology: h1 is reservation server; h2-h4 are clients; one OVS switch."""
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def run():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    c0 = net.addController("c0", controller=RemoteController,
                           ip="127.0.0.1", port=6633)
    s1 = net.addSwitch("s1", protocols="OpenFlow10")
    hosts = []
    for i in range(1, 5):
        h = net.addHost(f"h{i}", ip=f"10.0.0.{i}/24")
        net.addLink(h, s1, bw=100, delay="2ms")
        hosts.append(h)
    net.start()
    # Give the root namespace a reachable address for the POX policy listener.
    s1.cmd("ip addr flush dev s1")
    s1.cmd("ip addr add 10.0.0.254/24 dev s1")
    s1.cmd("ip link set s1 up")
    info("\\n*** Fixed topology: h1=server; h2-h4=clients; s1=single switch\\n")
    info("*** Start server: h1 python3 server.py\\n")
    info("*** Start clients: h2 python3 client.py (or h3/h4)\\n")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    run()