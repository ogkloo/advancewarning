# iperf test

import abr_emulator.networking as network

from threading import Thread

def playback_wrapper(link, network_profiles):
    def worker():
        network.playback(link, network_profiles)

    thread = Thread(target=worker)
    return thread

# Fast-varying link between 100 and 10Mbps
profile = [network.RateChangeEvent(rate, duration) 
           for rate, duration in [(100, 15), (10, 15)]]

domains = [(1, 1)]
topo = network.MultiSwitchServerClient(domains)

net = network.NetCommander(topo)
                           
net.start([[(5000, 1000)]], [[(250, 250)]*1])

# Grab the first link and make it unlucky
unlucky_link = net.client_links()[0]
playback_wrapper(unlucky_link, profile).start()

client_iperf_out = [client.popen('iperf3 -s -p 5001 &') for client in net.clients()]

for server in net.servers():
    server_iperf_outs = [server.popen(f'iperf3 -c {client.IP()} -p 5001 -t 30 -f m -i 1 --udp --bitrate 100M') 
                         for client in net.clients()]
    for iperf_out in server_iperf_outs:
        streams = [stream.decode('utf-8') for stream in iperf_out.communicate()]
        for stream in streams:
            print(stream)
    
net.stop()