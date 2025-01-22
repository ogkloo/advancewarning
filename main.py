# Main for abr_emulator

import abr_emulator.networking as network

domains = [(1, 4)]
topo = network.MultiSwitchServerClient(domains)

net = network.NetCommander(topo, 
                           [[(100, 100)]], 
                           [[(100, 100), 
                             (100, 100), 
                             (100, 100), 
                             (100, 100)]])

net.start()

# Lower client downlink
for link in net.client_links():
    link.intf2.config(bw=2)

client_iperf_out = [client.popen('iperf3 -s -p 5001 &') for client in net.clients()]

for server in net.servers():
    server_iperf_outs = [server.popen(f'iperf3 -c {client.IP()} -p 5001 -t 10 -f m') 
                         for client in net.clients()]
    for iperf_out in server_iperf_outs:
        streams = [stream.decode('utf-8') for stream in iperf_out.communicate()]
        for stream in streams:
            print(stream)
    
net.stop()