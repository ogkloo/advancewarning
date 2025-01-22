# Main for abr_emulator

import abr_emulator.networking as network

domains = [(1, 4)]
topo = network.MultiSwitchServerClient(domains)

net = network.NetCommander(topo, 
                           [[(100, 100)]], 
                           [[(100, 100), (100, 100), (100, 100), (100, 100)]])

for link in net.client_links():
    link.intf2.config(bw=2)