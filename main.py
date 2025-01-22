# Main for abr_emulator

import abr_emulator.networking as network

domains = [(1, 4)]
topo = network.MultiSwitchServerClient(domains)

net = network.NetCommander(topo, [[(100, 100)]], [[(100, 100), (100, 100), (100, 100), (100, 100)]])