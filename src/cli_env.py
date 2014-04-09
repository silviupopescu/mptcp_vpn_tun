from mininet.topo import Topo
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.cli import CLI
from time import sleep

#    ____________s1_____________
#   /                           \
# h1                             h2
#   \____________  _____________/
#                s2
#
#
#   h1: - h1-eth0 - 10.0.0.1; MPTCP off
#       - h1-eth1 - 11.0.0.1; MPTCP off
#       - tun0    - 12.0.0.1; MPTCP on; UDP; over h1-eth0
#       - tun1    - 13.0.0.1; MPTCP on; TCP; over h1-eth1
#   h2: - h2-eth0 - 10.0.0.2; MPTCP off
#       - h2-eth1 - 11.0.0.2; MPTCP off
#       - tun0    - 12.0.0.2; MPTCP on; UDP; over h2-eth0
#       - tun1    - 13.0.0.2; MPTCP on; TCP; over h2-eth1

class MPTCPTopo( Topo ):
    def __init__( self ):
        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        leftHostName = self.addHost( 'h1' )
        rightHostName = self.addHost( 'h2' )

        switchUpName = self.addSwitch( 's1' )
#        switchDownName = self.addSwitch('s2')

        # Add links for up
        self.addLink( leftHostName, switchUpName )
        self.addLink( switchUpName, rightHostName )

        # Add links for down
#        self.addLink( leftHostName, switchDownName )
#        self.addLink( switchDownName, rightHostName )

if __name__ == '__main__':
#    setLogLevel('debug')
    net = Mininet(topo = MPTCPTopo())

    h1 = net.hosts[0]
    h2 = net.hosts[1]

    # Setup first host
#    h1.setIP('11.0.0.1', 8, 'h1-eth1')
    h1.cmd('ip link set dev h1-eth0 multipath off')
#    h1.cmd('ip link set dev h1-eth1 multipath off')
    h1.cmd('openvpn --daemon --remote 10.0.0.2 --proto udp --dev tun0 --ifconfig 12.0.0.1 12.0.0.2')
    h1.cmd('openvpn --daemon --remote 10.0.0.2 --proto tcp-server --dev tun1 --ifconfig 13.0.0.1 13.0.0.2')
#    h1.cmd('openvpn --daemon --remote 11.0.0.2 --proto tcp-server --dev tun1 --ifconfig 13.0.0.1 13.0.0.2')
    h1.cmd('ip link set dev tun0 multipath on')
    h1.cmd('ip link set dev tun1 multipath on')
    h1.cmd('ip rule add from 12.0.0.1 table 1')
    h1.cmd('ip route add 12.0.0.0/32 dev tun0 scope link table 1')
    h1.cmd('ip route add default dev tun0 table 1')
    h1.cmd('ip rule add from 13.0.0.1 table 2')
    h1.cmd('ip route add 13.0.0.0/32 dev tun1 scope link table 2')
    h1.cmd('ip route add default dev tun1 table 2')

    # Setup second host
#    h2.setIP('11.0.0.2', 8, 'h2-eth1')
    h2.cmd('ip link set dev h2-eth0 multipath off')
#    h2.cmd('ip link set dev h2-eth1 multipath off')
    h2.cmd('openvpn --daemon --remote 10.0.0.1 --proto udp --dev tun0 --ifconfig 12.0.0.2 12.0.0.1')
    h2.cmd('openvpn --daemon --remote 10.0.0.1 --proto tcp-client --dev tun1 --ifconfig 13.0.0.2 13.0.0.1')
#    h2.cmd('openvpn --daemon --remote 11.0.0.1 --proto tcp-client --dev tun1 --ifconfig 13.0.0.2 13.0.0.1')
    h2.cmd('ip link set dev tun0 multipath on')
    h2.cmd('ip link set dev tun1 multipath on')
    h2.cmd('ip rule add from 12.0.0.2 table 1')
    h2.cmd('ip route add 12.0.0.0/32 dev tun0 scope link table 1')
    h2.cmd('ip route add default dev tun0 table 1')
    h2.cmd('ip rule add from 13.0.0.2 table 2')
    h2.cmd('ip route add 13.0.0.0/32 dev tun1 scope link table 2')
    h2.cmd('ip route add default dev tun1 table 2')

    # TODO: use dummynet to perfom traffic shaping

    net.start()

    # TODO: find a more elegant manner of measuring bandwidth; the iperf() in
    # the Mininet API does not use the VPN IPs and can't be coerced to do so
    # TODO: filter iperf output some more; for some reason, using tr and cut
    # leads to an empty file
    h1.cmd('iperf -s -D')
    sleep(1)
    h2.cmd('iperf -c 12.0.0.1 -f k -t 10 2>&1 | tail -n 1 > iperf.log')
    h2.cmd("cat iperf.log | tr -s ' ' | cut -d' ' -f7 | tail -n 1 > iperf2.log")
    h1.cmd('killall iperf')
    with open('iperf2.log', 'r') as f:
        raw_data = f.read()
        val = int(raw_data)
        print val

    net.startTerms()
    CLI(net)
    net.stop()
