from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.cli import CLI

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
        leftHostName = self.addHost( 'h1' )
        rightHostName = self.addHost( 'h2' )

        switchUpName = self.addSwitch( 's1' )
        switchDownName = self.addSwitch('s2')

        # Add links for up
        self.addLink( leftHostName, switchUpName )
        self.addLink( switchUpName, rightHostName )

        # Add links for down
        self.addLink( leftHostName, switchDownName )
        self.addLink( switchDownName, rightHostName )

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
    CLI(net)
    net.stop()
