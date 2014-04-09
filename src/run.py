import sys
import logging
from os import remove
from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import OVSKernelSwitch
from time import strftime, localtime, sleep

#    -----------tun0------------
#   /                           \
# h1=============s1==============h2
#   \                           /
#    -----------tun1------------


class MPTCPTopo( Topo ):
    def __init__( self, **link_opts ):
        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        leftHost = self.addHost( 'h1' )
        rightHost = self.addHost( 'h2' )

        switchUp = self.addSwitch( 's1' )
#        switchDown = self.addSwitch('s2')

        # Add links for up
        self.addLink( leftHost, switchUp, **link_opts )
        self.addLink( switchUp, rightHost, **link_opts )

        # Add links for down
#        self.addLink( leftHost, switchDown, **link_opts )
#        self.addLink( switchDown, rightHost, **link_opts )

def run_test(logfile, num_tests, **link_opts):
    logging.basicConfig(filename=logfile, level=logging.DEBUG)

    topo = MPTCPTopo(**link_opts)
    net = Mininet(topo, link=TCLink, switch=OVSKernelSwitch)

    h1 = net.hosts[0]
    h2 = net.hosts[1]

    # Setup first host
    h1.cmd('ip link set dev h1-eth0 multipath off')
    h1.cmd('openvpn --daemon --remote 10.0.0.2 --proto udp --dev tun0 --ifconfig 12.0.0.1 12.0.0.2')
    h1.cmd('openvpn --daemon --remote 10.0.0.2 --proto tcp-server --dev tun1 --ifconfig 13.0.0.1 13.0.0.2')
    h1.cmd('ip link set dev tun0 multipath on')
    h1.cmd('ip link set dev tun1 multipath on')
    h1.cmd('ip rule add from 12.0.0.1 table 1')
    h1.cmd('ip route add 12.0.0.0/32 dev tun0 scope link table 1')
    h1.cmd('ip route add default dev tun0 table 1')
    h1.cmd('ip rule add from 13.0.0.1 table 2')
    h1.cmd('ip route add 13.0.0.0/32 dev tun1 scope link table 2')
    h1.cmd('ip route add default dev tun1 table 2')

    # Setup second host
    h2.cmd('ip link set dev h2-eth0 multipath off')
    h2.cmd('openvpn --daemon --remote 10.0.0.1 --proto udp --dev tun0 --ifconfig 12.0.0.2 12.0.0.1')
    h2.cmd('openvpn --daemon --remote 10.0.0.1 --proto tcp-client --dev tun1 --ifconfig 13.0.0.2 13.0.0.1')
    h2.cmd('ip link set dev tun0 multipath on')
    h2.cmd('ip link set dev tun1 multipath on')
    h2.cmd('ip rule add from 12.0.0.2 table 1')
    h2.cmd('ip route add 12.0.0.0/32 dev tun0 scope link table 1')
    h2.cmd('ip route add default dev tun0 table 1')
    h2.cmd('ip rule add from 13.0.0.2 table 2')
    h2.cmd('ip route add 13.0.0.0/32 dev tun1 scope link table 2')
    h2.cmd('ip route add default dev tun1 table 2')

    net.start()

    avg = 0.0

    for i in range(num_tests):
        h1.cmd('iperf -s -D')
        sleep(1)
        h2.cmd('iperf -c 12.0.0.1 -f k -t 60 2>&1 | tail -n 1 > iperf.log')
        h2.cmd("cat iperf.log | tr -s ' ' | cut -d' ' -f7 | tail -n 1 > iperf2.log")
        h1.cmd('killall iperf')
        with open('iperf2.log', 'r') as f:
            raw_data = f.read()
            avg += int(raw_data)

    avg /= num_tests

    net.stop()

    logging.info('%d %d %f' % (int(link_opts['delay'][:-2]),
                               link_opts['bw'],
                               avg))
    print '%d %d %f' % (int(link_opts['delay'][:-2]),
                               link_opts['bw'],
                               avg))

if __name__ == '__main__':
    num_runs = 1
#    run_test('test.log', 10, 1, bw=1, delay=1, loss=0, max_queue_size=16, use_htb=True)
    for bdw in range(10, 101, 10):
        for dly in range(1, 51, 10):
            run_test('test-%s.log' % (strftime('%Y-%m-%d_%H-%M-%S', localtime())),
                     num_runs,
                     bw=bdw,
                     delay='%dms' % (dly),
                     use_htb=True)
    remove('iperf.log')
    remove('iperf2.log')
