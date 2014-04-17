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

def setup_host(host, congestion_algo, **tun_opts):
    host.cmd('ip link set dev %s-eth0 multipath off' % host.name)
    host.cmd('sysctl -w net.mptcp.mptcp_checksum=0')
    host.cmd('sysctl -w net.ipv4.tcp_congestion_control=%s' % congestion_algo)
    host.cmd('sysctl -w net.core.rmem_max=%d'% (int(2.2*tun_opts['rcvbuf'])))
    host.cmd('sysctl -w net.core.wmem_max=%d'% (int(2.2*tun_opts['sndbuf'])))
    if tun_opts['udp']:
        bdp_pages = int(1.1 * tun_opts['sndbuf'] / 4096)
        udp_mem='%d %d %d' % (bdp_pages, bdp_pages, bdp_pages)
        host.cmd('sysctl -w net.ipv4.udp_mem="%s"' % (udp_mem))
        host.cmd('sysctl -w net.ipv4.udp_rmem_min=%d' % (tun_opts['rcvbuf']))
        host.cmd('sysctl -w net.ipv4.udp_wmem_min=%d' % (tun_opts['sndbuf']))
        tun_cmd = ("openvpn --daemon "
                   "--remote %s "
                   "--proto udp --dev tun0 "
                   "--sndbuf %d --rcvbuf %d "
                   "--txqueuelen %d "
                   "--ifconfig %s %s"
                   % (tun_opts['udp_peer'], tun_opts['sndbuf'],
                      tun_opts['rcvbuf'], tun_opts['txqueuelen'],
                      tun_opts['udp_src'], tun_opts['udp_dst']))
        print tun_cmd
        host.cmd(tun_cmd)
        host.cmd('ip link set dev tun0 multipath on')
        host.cmd('ip rule add from %s table 1' % (tun_opts['udp_src']))
        host.cmd('ip route add %s/32 dev tun0 scope link table 1'
                 % (tun_opts['udp_src']))
        host.cmd('ip route add default dev tun0 table 1')
    if tun_opts['tcp']:
        bdp_pages = int(1.1 * 2 * tun_opts['sndbuf'] / 4096) # 2x for TCP
        tcp_mem='%d %d %d' % (bdp_pages, bdp_pages, bdp_pages)
        host.cmd('sysctl -w net.ipv4.tcp_mem="%s"' % (tcp_mem))
        tcp_rmem='%d %d %d' % (int(2.2 * tun_opts['rcvbuf']),
                               int(2.2 * tun_opts['rcvbuf']),
                               int(2.2 * tun_opts['rcvbuf']))
        host.cmd('sysctl -w net.ipv4.tcp_rmem="%s"' % (tcp_rmem))
        tcp_wmem='%d %d %d' % (int(2.2 * tun_opts['sndbuf']),
                               int(2.2 * tun_opts['sndbuf']),
                               int(2.2 * tun_opts['sndbuf']))
        host.cmd('sysctl -w net.ipv4.tcp_wmem="%s"' % (tcp_wmem))
        proto = 'tcp-server' if tun_opts['tcp_server'] else 'tcp-client'
        tun_cmd = ("openvpn --daemon "
                   "--remote %s "
                   "--proto %s --dev tun1 "
                   "--sndbuf %d --rcvbuf %d "
                   "--txqueuelen %d "
                   "--ifconfig %s %s"
                   % (tun_opts['tcp_peer'], proto, 2*tun_opts['sndbuf'],
                      2*tun_opts['rcvbuf'], tun_opts['txqueuelen'],
                      tun_opts['tcp_src'], tun_opts['tcp_dst']))
        print tun_cmd
        host.cmd(tun_cmd)
        host.cmd('ip link set dev tun1 multipath on')
        host.cmd('ip rule add from %s table 2' % (tun_opts['tcp_src']))
        host.cmd('ip route add %s/32 dev tun1 scope link table 2'
                 % (tun_opts['tcp_src']))
        host.cmd('ip route add default dev tun1 table 2')


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
    #mtu = 1500
    #sndbuf = bdp
    #rcvbuf = bdp
    #txqueuelen = 0 #int(ceil(float(bdp) / mtu))

    net.start()

    # Setup first host
    setup_host(h1, args.congestion, sndbuf=bdp, rcvbuf=bdp, txqueuelen=0,
               udp=args.udp,
               udp_peer='10.0.0.2', udp_src='12.0.0.1', udp_dst='12.0.0.2',
               tcp=args.tcp,
               tcp_peer='10.0.0.2', tcp_src='13.0.0.1', tcp_dst='13.0.0.2',
               tcp_server=True)

    # Setup second host
    setup_host(h2, args.congestion, sndbuf=bdp, rcvbuf=bdp, txqueuelen=0,
               udp=args.udp,
               udp_peer='10.0.0.1', udp_src='12.0.0.2', udp_dst='12.0.0.1',
               tcp=args.tcp,
               tcp_peer='10.0.0.1', tcp_src='13.0.0.2', tcp_dst='13.0.0.1',
               tcp_server=False)

    if not(args.udp and args.tcp):
        h1.cmd('sysctl -w net.ipv4.tcp_congestion_control="cubic"')
        h1.cmd('sysctl -w net.mptcp.mptcp_enabled=0')
        h2.cmd('sysctl -w net.ipv4.tcp_congestion_control="cubic"')
        h2.cmd('sysctl -w net.mptcp.mptcp_enabled=0')

    server_addr = '12.0.0.1'
    if args.tcp:
        server_addr = '13.0.0.1'

    avg = 0.0
    h1.cmd('iperf -s -D')
    for i in range(args.runs):
        h2.cmd('iperf -c %s -f k -t %d 2>&1 | tail -n 1 > iperf.log'
               % (server_addr, args.duration))
        h2.cmd("cat iperf.log | tr -s ' ' | cut -d' ' -f7 | tail -n 1  > iperf2.log")
        with open('iperf2.log', 'r') as f:
            raw_data = f.read()
            avg += int(raw_data.strip())
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
    parser.add_argument('-v', '--version', action='store_true', help='version')
    args = parser.parse_args()

    if args.version:
        print 'MPTCP/OpenVPN tester v2.0'

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
