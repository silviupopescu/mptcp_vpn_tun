from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet

#    ____________s1_____________
#   /                           \
# h1                             h2
#   \____________  _____________/
#                s2


class MPTCPTopo( Topo ):
    def __init__( self ):
        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        leftHost = self.addHost( 'h1' )
        rightHost = self.addHost( 'h2' )

        switchUp = self.addSwitch( 's1' )
        switchDown = self.addSwitch('s2')

        # Add links for up
        self.addLink( leftHost, switchUp )
        self.addLink( switchUp, rightHost )

        # Add links for down
        self.addLink( leftHost, switchDown )
        self.addLink( switchDown, rightHost )


if __name__ == '__main__':
#    setLogLevel('debug')
    net = Mininet(topo = MPTCPTopo())

    h1 = net.hosts[0]
    h2 = net.hosts[1]

    h1.setIP('11.0.0.1', 8, 'h1-eth1')
    h1.cmd('ip rule add from 10.0.0.1 table 1')
    h1.cmd('ip rule add from 11.0.0.1 table 2')
    h1.cmd('ip route add 10.0.0.0/8 dev h1-eth0 scope link table 1')
    h1.cmd('ip route add default dev h1-eth0 table 1')
    h1.cmd('ip route add 11.0.0.0/8 dev h1-eth1 scope link table 2')
    h1.cmd('ip route add default dev h1-eth1 table 2')

    h2.setIP('11.0.0.2', 8, 'h2-eth1')
    h2.cmd('ip rule add from 10.0.0.2 table 1')
    h2.cmd('ip rule add from 11.0.0.2 table 2')
    h2.cmd('ip route add 10.0.0.0/8 dev h2-eth0 scope link table 1')
    h2.cmd('ip route add default dev h2-eth0 table 1')
    h2.cmd('ip route add 11.0.0.0/8 dev h2-eth1 scope link table 2')
    h2.cmd('ip route add default dev h2-eth1 table 2')

    net.start()
    h1, h2 = net.get('h1', 'h2')
    avg = 0.0
    for i in range(10):
        res = net.iperf((h1, h2))
        if res[0].find('Mbits') != -1:
            res[0] = '0.' + res[0]
        if res[1].find('Mbits') != -1:
            res[1] = '0.' + res[1]
        avg += (float(res[0].split(' ')[0]) + float(res[1].split(' ')[0]))/2.0
    avg /= 10.0
    print "=================================================="
    print "Average is %f" % avg
    net.stop()
