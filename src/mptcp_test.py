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

def setup_core(host, algo, bdw, dly, factor):
    host.cmd('ip link set dev %s-eth0 multipath off' % host.name)
    host.cmd('sysctl -w net.mptcp.mptcp_checksum=0')
    host.cmd('sysctl -w net.ipv4.tcp_congestion_control="%s"' % algo)
    buffer_size = int(factor * bdw * dly * 125) # from Mbps*ms to bytes
    host.cmd('sysctl -w net.core.rmem_max=%d' % buffer_size)
    host.cmd('sysctl -w net.core.wmem_max=%d' % buffer_size)
    host.cmd('sysctl -w net.ipv4.inet_peer_maxttl=0')
    host.cmd('sysctl -w net.ipv4.inet_peer_minttl=0')
    host.cmd('sysctl -w net.ipv4.inet_peer_threshold=0')
    host.cmd('sysctl -w net.ipv4.route.flush=1')

def setup_udp(host, bdw, dly, txqueuelen, factor, shaper, peer_ip):
    buf_size = int(factor * bdw * dly * 125)
    buf_pages = buf_size / 4096
    host.cmd('sysctl -w net.ipv4.udp_mem="%d %d %d"' % (buf_pages, buf_pages,
                                                        buf_pages))
    host.cmd('sysctl -w net.ipv4.udp_rmem_min=%d' % buf_size)
    host.cmd('sysctl -w net.ipv4.udp_wmem_min=%d' % buf_size)
    src, dst = ('12.0.0.1', '12.0.0.2') if host.name == 'h1' else ('12.0.0.2',
                                                                   '12.0.0.1')
    host.cmd('openvpn --daemon --remote %s --proto udp --dev tun0'
             '--sndbuf %d --rcvbuf %d --txqueuelen %d'
             '--ifconfig %s %s --cipher none --auth none --fragment 0'
             '--mssfix 0 --tun-mtu 10000'
             % (peer_ip, buf_size, buf_size, txqueuelen, src, dst))
    host.cmd('ip link set dev tun0 multipath on')
    host.cmd('ip rule add from %s table 1' % src)
    host.cmd('ip route add %s/32 dev tun0 scope link table 1' % src)
    host.cmd('ip route add default dev tun0 table 1')
    if shaper == 'dummynet':
        host.cmd('ipfw add pipe 1 from %s to %s' % (src, dst))
        host.cmd('ipfw add pipe 2 from %s to %s' % (dst, src))
        host.cmd('ipfw pipe 1 config delay %dms bw %dMbit/s' % (dly, bdw))
        host.cmd('ipfw pipe 2 config delay %dms bw %dMbit/s' % (dly, bdw))

def setup_tcp(host, bdw, dly, txqueuelen, factor, shaper, peer_ip):
    buf_size = int(factor * bdw * dly * 125)
    buf_pages = buf_size / 4096
    host.cmd('sysctl -w net.ipv4.tcp_mem="%d %d %d"' % (buf_pages, buf_pages,
                                                        buf_pages))
    host.cmd('sysctl -w net.ipv4.tcp_rmem="%d %d %d"' % (buf_pages, buf_pages,
                                                         buf_pages))
    host.cmd('sysctl -w net.ipv4.tcp_wmem="%d %d %d"' % (buf_pages, buf_pages,
                                                         buf_pages))
    proto = 'tcp-server' if host.name == 'h1' else 'tcp-client'
    src, dst = ('13.0.0.1', '13.0.0.2') if host.name == 'h1' else ('13.0.0.2',
                                                                   '13.0.0.1')
    host.cmd('openvpn --daemon --remote %s --proto %s --dev tun1'
             '--sndbuf %d --rcvbuf %d --txqueuelen %d'
             '--ifconfig %s %s --cipher none --auth none --fragment 0'
             '--mssfix 0 --tun-mtu 10000'
             % (peer_ip, proto, buf_size, buf_size, txqueuelen, src, dst))
    host.cmd('ip link set dev tun1 multipath on')
    host.cmd('ip rule add from %s table 1' % src)
    host.cmd('ip route add %s/32 dev tun1 scope link table 1' % src)
    host.cmd('ip route add default dev tun1 table 1')
    if shaper == 'dummynet':
        host.cmd('ipfw add pipe 1 from %s to %s' % (src, dst))
        host.cmd('ipfw add pipe 2 from %s to %s' % (dst, src))
        host.cmd('ipfw pipe 1 config delay %dms bw %dMbit/s' % (dly, bdw))
        host.cmd('ipfw pipe 2 config delay %dms bw %dMbit/s' % (dly, bdw))

def setup_host(host, bdw, dly, txqueuelen, args, peer_ip):
    setup_core(host, args.congestion, bdw, dly, args.factor)
    if args.udp:
        setup_udp(host, bdw, dly, txqueuelen, args.factor, args.shaper, peer_ip)
    if args.tcp:
        setup_tcp(host, bdw, dly, txqueuelen, args.factor, args.shaper, peer_ip)

def run_test(args, bdw, dly):
    link_opts = {}
    if args.shaper == 'tc':
        link_opts = { 'bw':bdw, 'delay': '%dms' % dly, 'use_htb':True }

    topo = MPTCPTopo(**link_opts)
    net = Mininet(topo, switch=OVSKernelSwitch)
    if args.shaper == 'tc':
        net = Mininet(topo, link=TCLink, switch=OVSKernelSwitch)

    h1 = net.hosts[0]
    h2 = net.hosts[1]

    net.start()

    # Setup first host
    setup_host(h1, bdw, dly, 0, args, h2.IP(intf='h2-eth0'))

    # Setup second host
    setup_host(h2, bdw, dly, 0, args, h1.IP(intf='h1-eth0'))

    if not(args.udp and args.tcp):
        h1.cmd('sysctl -w net.ipv4.tcp_congestion_control="cubic"')
        h1.cmd('sysctl -w net.mptcp.mptcp_enabled=0')
        h2.cmd('sysctl -w net.ipv4.tcp_congestion_control="cubic"')
        h2.cmd('sysctl -w net.mptcp.mptcp_enabled=0')

    server_addr = '12.0.0.1'
    if args.tcp:
        server_addr = '13.0.0.1'

    avg = 0.0
    if args.perf == 'iperf':
        h1.cmd('iperf -s -D')
        for i in range(args.runs):
            p1 = h2.popen('iperf -c %s -f k -t %d' % (server_addr,
                                                      args.duration),
                          stdout=subprocess.PIPE)
            out = p1.communicate()[0].split('\n')[-2].split()[6]
            avg += float(out)
        h1.cmd('killall iperf')
    else:
        h1.cmd('netserver -4 -p 5001')
        for i in range(args.runs):
            p1 = h2.popen('netperf -H %s -f k -p 5001 -l %d' % (server_addr,
                                                                args.duration),
                          stdout=subprocess.PIPE)
            out = p1.communicate()[0].split('\n')[6].split()[4]
            avg += float(out)
        h1.cmd('killall netserver')
    avg /= args.runs
    h1.cmd('killall openvpn')
    h2.cmd('killall openvpn')

    net.stop()

    logging.info('%d %d %f' % (dly, bdw, avg))
    print '%d %d %f' % (dly, bdw, avg)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="""run MPTCP over OpenVPN
                                     throughput tests""")
    parser.add_argument('-f', '--factor', type=float, default=1.0,
                        help='buffer size = factor * BDP')
    parser.add_argument('-u', '--udp', action='store_true',
                        help='create a UDP tunnel')
    parser.add_argument('-t', '--tcp', action='store_true',
                        help='create a TCP tunnel')
    parser.add_argument('-nr', '--runs', type=int, default=3,
                        help='how many times to run a test')
    parser.add_argument('-c', '--congestion', choices=['cubic', 'olia'],
                        default='olia', help='TCP congestion algorithm')
    parser.add_argument('-bf', '--bandwidth-from', type=int, default=100,
                        help='bandwidth start value (Mbps)')
    parser.add_argument('-bs', '--bandwidth-step', type=int, default=-10,
                        help='bandwidth step value (Mbps)')
    parser.add_argument('-bt', '--bandwidth-to', type=int, default=9,
                        help='bandwidth stop value (Mbps)')
    parser.add_argument('-df', '--delay-from', type=int, default=50,
                        help='delay start value (ms)')
    parser.add_argument('-ds', '--delay-step', type=int, default=-10,
                        help='delay step value (ms)')
    parser.add_argument('-dt', '--delay-to', type=int, default=9,
                        help='delay stop value (ms)')
    parser.add_argument('-d', '--duration', type=int, default=10,
                        help='iperf duration (s)')
    parser.add_argument('-p', '--perf', choices=['iperf', 'netperf'],
                        default='iperf',
                        help='Program to run bandwidth test')
    parser.add_argument('-s', '--shaper', choices=['tc', 'dummynet'],
                        default='tc',
                        help='Program that limits bandwidth and delay.')
    parser.add_argument('-v', '--version', action='store_true', help='version')
    args = parser.parse_args()

    if args.version:
        print 'MPTCP/OpenVPN tester v2.0'

    logfile = 'test-%s-%s-%s%s%f-%s.log' % (args.shaper, args.perf,
                                            'udp-' if args.udp else '',
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
            run_test(args, bdw, dly)
