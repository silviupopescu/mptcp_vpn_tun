from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet

# h1-----s1-----h2


class MPTCPTopo( Topo ):
    def __init__( self ):
        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        leftHost = self.addHost( 'h1' )
        rightHost = self.addHost( 'h2' )

        switchUp = self.addSwitch( 's1' )

        # Add links for up
        self.addLink( leftHost, switchUp )
        self.addLink( switchUp, rightHost )

if __name__ == '__main__':
#    setLogLevel('debug')
    net = Mininet(topo = MPTCPTopo())

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
