import logging
from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.link import TCLink

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

def run_test(logfile, num_tests, cwnd, **link_opts):
    logging.basicConfig(filename=logfile, level=logging.DEBUG)

    topo = MPTCPTopo(**link_opts)
    net = Mininet(topo, link=TCLink)

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

    # run 10 tests and measure the average
    for i in range(num_tests):
        res = net.iperf((h1, h2))
        if res[0].find('Mbits') != -1:
            res[0] = '0.' + res[0]
        if res[1].find('Mbits') != -1:
            res[1] = '0.' + res[1]
        avg += (float(res[0].split(' ')[0]) + float(res[1].split(' ')[0]))/2.0
    avg /= float(num_tests)

    net.stop()

    logging.info(cwnd)
    logging.info(link_opts)
    logging.info(avg)


if __name__ == '__main__':
    # TODO:
    # cwnd between 1 and 122 with a step of 10
    # bw between 1Mbps and 16Gbps with a geometric ratio of 2
    # delay between 0 (inclusive) and 100ms with a step of 10
    # loss between 0 (inclusive) and 50% with a step of 10; consider pinning at 0 since 10% reduces throughput greatly
    # max_queue_size between 16 and 4096 with a geometric ration of 2; consider calculating limits based on cwnd and bw
    # use a test count variable which is incremented at the innermost loop
    # use test count and other info to generate filename dinamically
    run_test('test.log', 10, 3, bw=10, delay='5ms', loss=10, max_queue_size=1000, use_htb=True)
