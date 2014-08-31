import sys
import logging
import os
from time import strftime, localtime, sleep
from math import ceil
import argparse
import platform
import subprocess

#    -----------tun0------------
#   /                           \
# h1=============s1==============h2
#   \                           /
#    -----------tun1------------

peer_presets = {'smother3':['10.42.129.138', '12.0.0.1', '13.0.0.1'],
                'smother4':['10.42.130.134', '12.0.0.2', '13.0.0.2']}

def setup_core(algo, bdw, dly, factor, scheduler):
    subprocess.call(['ip', 'link', 'set', 'dev', 'eth0', 'multipath', 'off'])
    subprocess.call(['sysctl', '-w', 'net.mptcp.mptcp_checksum=0'])
    os.system('sysctl -w net.ipv4.tcp_congestion_control="%s"' % algo)
#    subprocess.call(['sysctl', '-w', 'net.ipv4.tcp_congestion_control=%s' % algo])
    buffer_size = int(factor * bdw * dly * 125) # 125 converts from Mbps*ms to bytes
    subprocess.call(['sysctl', '-w', 'net.core.rmem_max=%d' % buffer_size])
    subprocess.call(['sysctl', '-w', 'net.core.wmem_max=%d' % buffer_size])
    subprocess.call(['sysctl', '-w', 'net.ipv4.inet_peer_maxttl=0'])
    subprocess.call(['sysctl', '-w', 'net.ipv4.inet_peer_minttl=0'])
    subprocess.call(['sysctl', '-w', 'net.ipv4.inet_peer_threshold=0'])
    subprocess.call(['sysctl', '-w', 'net.ipv4.route.flush=1'])
    subprocess.call(['tc', 'qdisc', 'del', 'dev', 'eth0', 'root'])
    subprocess.call(['tc', 'qdisc', 'add', 'dev', 'eth0', 'root',
                     'handle', '1:', scheduler])
    spec = scheduler + ' rt' if scheduler == 'hfsc' else 'htb'
    subprocess.call(['tc', 'class', 'add', 'dev', 'eth0', 'parent', '1:',
                     'classid', '1:1', spec, 'rate', '%dmbit' % bdw])
    if dly != 0:
        subprocess.call(['tc', 'qdisc', 'add', 'dev', 'eth0', 'parent', '1:1',
                         'handle', '12', 'netem', 'delay', '%dms' % dly])
    # filter iperf/netperf (5001)
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'dport', '5001', '0xffff', 'flowid', '1:1'])
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'sport', '5001', '0xffff', 'flowid', '1:1'])
    # filter openvpn(443, 943, 1194)
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'dport', '443', '0xffff', 'flowid', '1:1'])
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'sport', '443', '0xffff', 'flowid', '1:1'])
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'dport', '943', '0xffff', 'flowid', '1:1'])
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'sport', '943', '0xffff', 'flowid', '1:1'])
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'dport', '1194', '0xffff', 'flowid', '1:1'])
    subprocess.call(['tc', 'filter', 'add', 'dev', 'eth0', 'protocol', 'ip',
                     'parent', '1:', 'prio', '1', 'u32', 'match', 'ip',
                     'sport', '1194', '0xffff', 'flowid', '1:1'])

def setup_udp(host, bdw, dly, txqueuelen, factor):
    bdp = int(factor * bdw * dly * 125)
    bdp_pages = bdp / 4096
    udp_mem = '%d %d %d' % (bdp_pages, bdp_pages, bdp_pages) # min, pressure, max
    os.system('sysctl -w net.ipv4.udp_mem="%s"' % udp_mem)
#    subprocess.call(['sysctl', '-w', 'net.ipv4.udp_mem="%s"' % udp_mem])
    subprocess.call(['sysctl', '-w', 'net.ipv4.udp_rmem_min=%d' % bdp])
    subprocess.call(['sysctl', '-w', 'net.ipv4.udp_wmem_min=%d' % bdp])
    server_name = peer_presets.keys()[0]
    client_name = peer_presets.keys()[1]
    peer = peer_presets[client_name][0] if host == server_name else peer_presets[server_name][0]
    src = peer_presets[server_name][1] if host == server_name else peer_presets[client_name][1]
    dst = peer_presets[client_name][1] if host == server_name else peer_presets[server_name][1]
    subprocess.call(['openvpn', '--daemon', '--remote', peer, '--proto', 'udp',
                     '--dev', 'tun0', '--sndbuf', str(bdp), '--rcvbuf',
                     str(bdp), '--txqueuelen', str(txqueuelen),
                     '--ifconfig', src, dst, '--cipher', 'none', '--auth',
                     'none', '--fragment', '0', '--mssfix', '0', '--tun-mtu',
                     '10000'])
    subprocess.call(['ip', 'link', 'set', 'dev', 'tun0', 'multipath', 'on'])
    subprocess.call(['ip', 'rule', 'add', 'from', src, 'table', '1'])
    subprocess.call(['ip', 'route', 'add', '%s/32' % src, 'dev', 'tun0',
                     'scope', 'link', 'table', '1'])
    subprocess.call(['ip', 'route', 'add', 'default', 'dev', 'tun0', 'table', '1'])

def setup_tcp(host, bdw, dly, txqueuelen, factor):
    bdp = int(factor * bdw * dly * 125)
    bdp_pages = bdp / 4096
    tcp_mem = '%d %d %d' % (bdp_pages, bdp_pages, bdp_pages) # min, pressure, max
    os.system('sysctl -w net.ipv4.tcp_mem="%s"' % tcp_mem)
#    subprocess.call(['sysctl', '-w', 'net.ipv4.tcp_mem="%s"' % tcp_mem])
    tcp_rmem = '%d %d %d' % (bdp, bdp, bdp) # min, default, max
    os.system('sysctl -w net.ipv4.tcp_rmem="%s"' % tcp_rmem)
#    subprocess.call(['sysctl', '-w', 'net.ipv4.tcp_rmem="%s"' % tcp_rmem])
    tcp_wmem = '%d %d %d' % (bdp, bdp, bdp) # min, default, max
    os.system('sysctl -w net.ipv4.tcp_wmem="%s"' % tcp_wmem)
#    subprocess.call(['sysctl', '-w', 'net.ipv4.tcp_wmem="%s"' % tcp_wmem])
    server_name = peer_presets.keys()[0]
    client_name = peer_presets.keys()[1]
    proto = 'tcp-server' if host == server_name else 'tcp-client'
    peer = peer_presets[client_name][0] if host == server_name else peer_presets[server_name][0]
    src = peer_presets[server_name][2] if host == server_name else peer_presets[client_name][2]
    dst = peer_presets[client_name][2] if host == server_name else peer_presets[server_name][2]
    subprocess.call(['openvpn', '--daemon', '--remote', peer, '--proto', proto,
                     '--dev', 'tun1', '--sndbuf', str(bdp), '--rcvbuf',
                     str(bdp), '--txqueuelen', str(txqueuelen),
                     '--ifconfig', src, dst, '--cipher', 'none', '--auth',
                     'none', '--fragment', '0', '--mssfix', '0', '--tun-mtu',
                     '10000'])
    subprocess.call(['ip', 'link', 'set', 'dev', 'tun1', 'multipath', 'on'])
    subprocess.call(['ip', 'rule', 'add', 'from', src, 'table', '2'])
    subprocess.call(['ip', 'route', 'add', '%s/32' % src, 'dev', 'tun1',
                     'scope', 'link', 'table', '2'])
    subprocess.call(['ip', 'route', 'add', 'default', 'dev', 'tun1', 'table', '2'])

def setup_host(host, algo, bdw, dly, txqueuelen, hasUDP, hasTCP, args):
    setup_core(algo, bdw, dly, args.factor, args.scheduler)
    if hasUDP:
        setup_udp(host, bdw, dly, txqueuelen, args.factor)
    if hasTCP:
        setup_tcp(host, bdw, dly, txqueuelen, args.factor)

def run_test(args, bdw, dly):
    #txqueuelen = 0 #int(ceil(float(bdp) / mtu))
    host = platform.node()
    setup_host(host, args.congestion, bdw, dly, 0, args.udp, args.tcp, args)

    if (not(args.udp and args.tcp)):
        os.system('sysctl -w net.ipv4.tcp_congestion_control="cubic"')
#        subprocess.call(['sysctl', '-w', 'net.ipv4.tcp_congestion_control="cubic"'])
        subprocess.call(['sysctl', '-w', 'net.mptcp.mptcp_enabled=0'])

    server_name = peer_presets.keys()[0]
    server_addr = peer_presets[server_name][1]
    if args.tcp:
        server_addr = peer_presets[server_name][2]

    if host == server_name:
        if args.perf == 'iperf':
            subprocess.call(['iperf', '-s'])
        else:
            subprocess.call(['netserver', '-D', '-4', '-p', '5001'])
        print 'killed local server'
    else:
        avg = 0.0
        for i in range(args.runs):
            out = ''
            if args.perf == 'iperf':
                p1 = subprocess.Popen(('iperf', '-c', server_addr, '-f', 'k', '-t',
                                       str(args.duration)), stdout=subprocess.PIPE)
                out = p1.communicate()[0].split('\n')[-2].split()[6]
            else:
                p1 = subprocess.Popen(('netperf', '-H', server_addr, '-f', 'k',
                                       '-p', '5001', '-l', str(args.duration)),
                                       stdout=subprocess.PIPE)
                out = p1.communicate()[0].split('\n')[6].split()[4]
            avg += float(out)
        avg /= args.runs
        subprocess.call(['ssh', '-i', 'default-key.key',
                         'root@' + peer_presets[server_name][0],
                         'smother_aux.sh'])
        logging.info('%d %d %f' % (dly, bdw, avg))
        print '%d %d %f' % (dly, bdw, avg)
    subprocess.call(['killall', 'openvpn'])

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
    parser.add_argument('-s', '--scheduler', choices=['htb', 'hfsc'],
                        default='htb', help='packet scheduler')
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
    parser.add_argument('-dt', '--delay-to', type=int, default=-1,
                        help='delay stop value (ms)')
    parser.add_argument('-d', '--duration', type=int, default=10,
                        help='test duration (s)')
    parser.add_argument('-p', '--perf', choices=['iperf', 'netperf'],
                        default='netperf',
                        help='Program to run bandwidth test')
    parser.add_argument('-v', '--version', action='store_true', help='version')
    args = parser.parse_args()

    if args.version:
        print 'MPTCP/OpenVPN tester v4.0 (Christina)'

    if args.perf == 'netperf':
        args.duration = 30
        args.runs = 1

    logfile = 'test-%s-%s%s%f-%s.log' % (args.perf,
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
