SMOTHER
=============
SMOTHER (Secure Multipath OstenTatiously Harassing Egress Restrictions) is
a system that allows users to bypass egress firewalls using MPTCP, OpenVPN and
tunneling traffic via common protocols.

MPTCP is used to provide the user the ability to create several tunnels, over
various underlying protocols (IP, TCP, UDP, DNS, HTTP) such that the total
outgoing bandwidth is maximized, provided there are several outgoing network
interfaces. Common cases include mobile devices (3G/4G/WiFi) and datacenters
(which have several links per node).

OpenVPN is used to encrypt outgoing traffic such that it true nature is not
obvious to network administrators and egress firewalls.

Because of issues pertaining to the deployment of MPTCP in the current Internet,
as well as lack of a real computer network, Mininet is used to model several
network nodes.
