from abr_emulator import networking as network
from abr_emulator import scheduler

from time import sleep
from threading import Thread

def playback_wrapper(link, network_profiles):
    def worker():
        network.playback(link, network_profiles)

    thread = Thread(target=worker)
    return thread

test = scheduler.TestCase(
    video_mpd='videos/academic/multi_resolution.mpd', 
    video_name='academic',
    abr='bandwidth',
    search_method='none',
    # Dummy
    net_condition=None,
    max_buffer=3.0,
    initial_quality=None,
    initial_buffer=None,
    use_quic=False,
    n=1)

# Fast-varying link between 100 and 10Mbps
profile = [network.RateChangeEvent(rate, duration) 
           for rate, duration in [(100, 1), (10, 1)]*15]

domains = [(1, 1)]
topo = network.MultiSwitchServerClient(domains)

net = network.NetCommander(topo)
                           
net.start([[(5000, 1000)]], [[(250, 250)]*1])

server = list(net.servers())[0]
client = list(net.clients())[0]

# Start server and wait a second for it to run
server.popen('http-server -p %d . &' % 8080)
sleep(2)

istream_out = test.run_test(server, client)

istream_out = [stream.decode('utf-8') for stream in istream_out.communicate()]

net.stop()

for stream in istream_out:
    print(stream)
