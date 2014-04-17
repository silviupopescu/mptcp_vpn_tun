import sys
import logging
from os import remove
from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import OVSKernelSwitch
from time import strftime, localtime, sleep
from math import ceil
import argparse

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

def run_test(args, **link_opts):

    topo = MPTCPTopo(**link_opts)
    net = Mininet(topo, link=TCLink, switch=OVSKernelSwitch)

    h1 = net.hosts[0]
    h2 = net.hosts[1]

    #BDP
    delay = int(link_opts['delay'][:-2])
    if delay == 0:
        delay = 1
    bdp = args.factor * link_opts['bw'] * delay * 125
    mtu = 1500
    sndbuf = bdp
    rcvbuf = bdp
    txqueuelen = 0 #int(ceil(float(bdp) / mtu))

    # Setup first host
    h1.cmd('ip link set dev h1-eth0 multipath off')
    h1.cmd('openvpn --daemon --remote 10.0.0.2 --proto udp --dev tun0 --sndbuf %d --rcvbuf %d --txqueuelen %d --ifconfig 12.0.0.1 12.0.0.2' % (sndbuf, rcvbuf, txqueuelen))
    h1.cmd('openvpn --daemon --remote 10.0.0.2 --proto tcp-server --dev tun1 --sndbuf %d --rcvbuf %d --txqueuelen %d --ifconfig 13.0.0.1 13.0.0.2' % (sndbuf, rcvbuf, txqueuelen))
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
    h2.cmd('openvpn --daemon --remote 10.0.0.1 --proto udp --dev tun0 --sndbuf %d --rcvbuf %d --txqueuelen %d --ifconfig 12.0.0.2 12.0.0.1' % (sndbuf, rcvbuf, txqueuelen))
    h2.cmd('openvpn --daemon --remote 10.0.0.1 --proto tcp-client --dev tun1 --sndbuf %d --rcvbuf %d --txqueuelen %d --ifconfig 13.0.0.2 13.0.0.1' % (sndbuf, rcvbuf, txqueuelen))
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

    h1.cmd('iperf -s -D')

    for i in range(args.runs):
        h2.cmd('iperf -c 12.0.0.1 -f k 2>&1 | tail -n 1 > iperf.log')
        h2.cmd("cat iperf.log | tr -s ' ' | cut -d' ' -f7 | tail -n 1 > iperf2.log")
        with open('iperf2.log', 'r') as f:
            raw_data = f.read()
            avg += int(raw_data)

    h1.cmd('killall iperf')

    avg /= args.runs

    net.stop()

    logging.info('%d %d %f' % (int(link_opts['delay'][:-2]),
                               link_opts['bw'],
                               avg))
    print '%d %d %f' % (int(link_opts['delay'][:-2]),
                               link_opts['bw'],
                               avg)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="""run MPTCP over OpenVPN
                                     throughput tests""")
    parser.add_argument('-f', '--factor', type=float, default=1.0,
                        help='buffer size = factor * BDP')
    parser.add_argument('-u', '--udp', action='store_true',
                        help='create a UDP tunnel')
    parser.add_argument('-t', '--tcp', action='store_true',
                        help='create a TCP tunnel')
    parser.add_argument('-nr', '--runs', type=int, default=5,
                        help='how many times to run a test')
    parser.add_argument('-c', '--congestion', choices=['cubic', 'olia'],
                        default='olia', help='TCP congestion algorithm')
    parser.add_argument('-bf', '--bandwidth-from', type=int, default=10,
                        help='bandwidth start value (Mbps)')
    parser.add_argument('-bs', '--bandwidth-step', type=int, default=10,
                        help='bandwidth step value (Mbps)')
    parser.add_argument('-bt', '--bandwidth-to', type=int, default=101,
                        help='bandwidth stop value (Mbps)')
    parser.add_argument('-df', '--delay-from', type=int, default=0,
                        help='delay start value (ms)')
    parser.add_argument('-ds', '--delay-step', type=int, default=10,
                        help='delay step value (ms)')
    parser.add_argument('-dt', '--delay-to', type=int, default=51,
                        help='delay stop value (ms)')
    parser.add_argument('-d', '--duration', type=int, default=10,
                        help='iperf duration (s)')
    args = parser.parse_args()

    logfile = 'test-%s%s%f-%s.log' % ('udp-' if args.udp else '',
                                      'tcp-' if args.tcp else '',
                                      args.factor,
                                      strftime('%Y-%m-%d_%H-%M-%S',
                                               localtime()))
    logging.basicConfig(filename=logfile,
                        level=logging.DEBUG,
                        format='%(message)s')

    for bdw in range(args.bandwidth_from, args.bandwidth_to,
                     args.bandwidth_step):
        for dly in range(args.delay_from, args.delay_to, args.delay_step):
            run_test(args, bw=bdw, delay='%dms' % (dly), use_htb=True)

    remove('iperf.log')
    remove('iperf2.log')
