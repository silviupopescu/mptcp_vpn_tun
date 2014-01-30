import logging
from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import OVSKernelSwitch
from time import strftime, localtime

#    ____________s1_____________
#   /                           \
# h1                             h2
#   \____________  _____________/
#                s2


class MPTCPTopo( Topo ):
    def __init__( self, **link_opts ):
        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        leftHost = self.addHost( 'h1' )
        rightHost = self.addHost( 'h2' )

        switchUp = self.addSwitch( 's1' )
        switchDown = self.addSwitch('s2')

        # Add links for up
        self.addLink( leftHost, switchUp, **link_opts )
        self.addLink( switchUp, rightHost, **link_opts )

        # Add links for down
        self.addLink( leftHost, switchDown, **link_opts )
        self.addLink( switchDown, rightHost, **link_opts )

def get_speed_in_bps(speed_str):
    speed, unit = speed_str.split(' ')
    speed = float(speed)
    unit_factor = 1
    if unit.lower().find('gbits') != -1:
        unit_factor = 1000000000
    elif unit.lower().find('mbits') != -1:
        unit_factor = 1000000
    elif unit.lower().find('kbits') != -1:
        unit_factor = 1000
    speed *= unit_factor
    return speed

def run_test(logfile, num_tests, cwnd, **link_opts):
    logging.basicConfig(filename=logfile, level=logging.DEBUG)

    topo = MPTCPTopo(**link_opts)
    net = Mininet(topo, link=TCLink, switch=OVSKernelSwitch)

    h1 = net.hosts[0]
    h2 = net.hosts[1]

    # Set routes with congestion window and receive window for first host
    h1.setIP('11.0.0.1', 8, 'h1-eth1')
    h1.cmd('ip rule add from 10.0.0.1 table 1')
    h1.cmd('ip rule add from 11.0.0.1 table 2')
    h1.cmd('ip route add 10.0.0.0/8 dev h1-eth0 scope link table 1')
    h1.cmd('ip route add default dev h1-eth0 table 1')
    h1.cmd('ip route add 11.0.0.0/8 dev h1-eth1 scope link table 2')
    h1.cmd('ip route add default dev h1-eth1 table 2')
    h1.cmd('ip route change default initcwnd %d initrwnd %d' % (cwnd, cwnd))
    h1.cmd('ip route flush cache')

    # Set routes with congestion window and receive window for second host
    h2.setIP('11.0.0.2', 8, 'h2-eth1')
    h2.cmd('ip rule add from 10.0.0.2 table 1')
    h2.cmd('ip rule add from 11.0.0.2 table 2')
    h2.cmd('ip route add 10.0.0.0/8 dev h2-eth0 scope link table 1')
    h2.cmd('ip route add default dev h2-eth0 table 1')
    h2.cmd('ip route add 11.0.0.0/8 dev h2-eth1 scope link table 2')
    h2.cmd('ip route add default dev h2-eth1 table 2')
    h2.cmd('ip route change default initcwnd %d initrwnd %d' % (cwnd, cwnd))
    h2.cmd('ip route flush cache')

    net.start()

    h1, h2 = net.get('h1', 'h2')
    avg = 0.0

    for i in range(num_tests):
        res = net.iperf((h1, h2))
        up_speed = get_speed_in_bps(res[0])
        down_speed = get_speed_in_bps(res[1])
        avg += (up_speed + down_speed)/2.0

    avg /= num_tests

    net.stop()

    logging.info('%d %d %d %d %d %f' % (cwnd, int(link_opts['delay'][:-2]),
                                        link_opts['loss'], link_opts['bw'],
                                        link_opts['max_queue_size'], avg))

if __name__ == '__main__':
    # TODO:
    # cwnd between 10 and 122 with a step of 20
    # bw between 1Mbps and 16Gbps with a geometric ratio of 2
    # delay between 0 (inclusive) and 100ms with a step of 20
    # max_queue_size between 64 and 4096 with a geometric ration of 2; consider calculating limits based on cwnd and bw
    num_runs = 1
#    run_test('test.log', 10, 1, bw=1, delay=1, loss=0, max_queue_size=16, use_htb=True)
    for cwnd in range(10, 122, 20):
        for bdw in map(lambda x: 2 ** x, range(12, 15)):
            for dly in range(0, 102, 20):
                #for lss in range(0, 51, 10):
                lss = 0
                for mqs in map(lambda x: 2 ** x, range(6, 13)):
                    run_test('test-%s.log' % (strftime('%Y-%m-%d_%H-%M-%S', localtime())),
                             num_runs,
                             cwnd,
                             bw=bdw,
                             delay='%dms' % (dly),
                             loss=lss,
                             max_queue_size=mqs,
                             use_htb=True)
