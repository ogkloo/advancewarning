from enum import Enum
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCIntf
from mininet.util import custom, dumpNodeConnections
from mininet.log import setLogLevel
from mininet.clean import cleanup

from time import sleep
import json
#import numpy as np
from dataclasses import dataclass
from typing import List, Callable
import argparse
import os
import threading
import itertools
import uuid

DEFAULTS = {
    'format': 'm',
    'istream': './istream-player/istream',
    'predictions_file': 'mininet_predictions_file.json',
    'tmpdir': 'tmp',
    'results_dir': 'results',
    'connectivity_results_dir': 'iperf',
    'notifier': './istream-player/send_event.sh',
    'quictun-client': './quictun/quictun-client',
    'quictun-server': './quictun/quictun-server',
    'iperf-port': 5201,
    'http-port': 8080,
    'cushion': 2,
}

@dataclass
class RateChangeEvent():
    new_rate: float
    duration: float

@dataclass
class NotifyEvent():
    notification_time: float
    outage_duration: float
    last_valid: float

    start_rate: float
    outage_rate: float
    end_rate: float

    def to_string(self):
        return f'{self.start_rate},{self.outage_rate},{self.end_rate},{self.notification_time},{self.outage_duration},{self.last_valid}'

@dataclass
class InactiveNotify():
    event_type: 'str'


class NetworkProfile():
    def __init__(self, initial_rate, outage_rate, new_rate, before_time, notify_time, outage_time, valid_time, after_time):
        self.summary = f'{initial_rate}, {outage_rate}, {new_rate}, {before_time}, {notify_time}, {outage_time}, {valid_time}, {after_time}'

        self.initial_rate = initial_rate
        self.outage_rate = outage_rate
        self.new_rate = new_rate
        self.before_time = before_time
        self.notify_time = notify_time
        self.outage_time = outage_time
        self.valid = valid_time
        self.after_time = after_time

        self.profile = [RateChangeEvent(initial_rate, before_time-notify_time), 
                        NotifyEvent(notify_time, outage_time, valid_time, initial_rate, outage_rate, new_rate),
                        RateChangeEvent(initial_rate, notify_time),
                        RateChangeEvent(outage_rate, outage_time), 
                        InactiveNotify('stop'),
                        RateChangeEvent(new_rate, after_time)]
    
    def summarize(self):
        return self.summary

    def get_duration(self):
        return self.before_time + self.outage_time + self.after_time
    
    def to_json(self):
        return {
            'initial_rate': self.initial_rate,
            'outage_rate': self.outage_rate,
            'new_rate': self.new_rate,
            'before_time': self.before_time,
            'notify_time': self.notify_time,
            'outage_time': self.outage_time,
            'valid': self.valid,
            'after_time': self.after_time
        }

@dataclass
class TestCase():
    @dataclass
    class Video():
        name: str
        url: str

    video: Video
    abr: str
    search_method: str
    net_condition: List[RateChangeEvent | NotifyEvent | InactiveNotify]
    max_buffer: float
    initial_quality: int
    initial_buffer: float
    proto: str
    n: int

    def __init__(self, video_mpd, video_name, abr, search_method, net_condition, max_buffer, initial_quality, initial_buffer, proto, n):
        self.uuid = uuid.uuid4()

        self.video = self.Video(video_name, video_mpd)
        self.abr = abr
        self.search_method = search_method
        self.net_condition = net_condition
        self.max_buffer = max_buffer
        self.initial_quality = initial_quality
        self.initial_buffer = initial_buffer
        self.proto = proto
        self.n = n

    def manifest(self):
        return {'filename': str(self.uuid),
                'video_name': self.video.name,
                'video_mpd': self.video.url,
                'abr': self.abr,
                'search_method': self.search_method,
                'network': self.net_condition.to_json(),
                'max_buffer': self.max_buffer,
                'initial_quality': self.initial_quality,
                'initial_buffer': self.initial_buffer,
                'proto': self.proto,
                'n': self.n}

@dataclass
class TestDescription():
    test_cases: List[TestCase]

    # Top level results directory
    results_dir: str

    # If true, run an iperf test on each unique network profile in the test
    # set. The results are stored at results_dir/iperf_results_dir.
    run_iperf_first: bool = False
    iperf_results_dir: str = 'iperf'

    # Whether or not to write the logs which istream writes to stderr. 
    # Since these can be quite large, it is recommended to disable them
    # if filesize is a concern and you won't need detailed log information.
    write_logs: bool = True
    write_headers: bool = True

    # Whether or not to overwrite previous tests.
    overwrite: bool = True

    # How often to print out done/test_cases while running tests.
    update: int = 10

    def mk_test_cases(self, 
                      videos, 
                      rates, 
                      durations, 
                      notify_times, 
                      abrs, 
                      search_methods,
                      max_buffers, 
                      initial_qualities, 
                      initial_buffers, 
                      protos, 
                      N):
        for case in itertools.product(videos,
                                      rates,
                                      durations,
                                      notify_times,
                                      abrs,
                                      search_methods,
                                      max_buffers,
                                      initial_qualities,
                                      initial_buffers, 
                                      protos,
                                      range(0,N)):
            video, rate_trio, duration_trio, notification_trio, abr, search_method, max_buffer, initial_quality, initial_buffer, proto, n = case
            video_url, video_name = video
            initial_rate, outage_rate, new_rate = rate_trio
            before_time, outage_time, after_time = duration_trio
            notify_time, last_valid = notification_trio

            network_conditions = NetworkProfile(initial_rate, 
                                                outage_rate, 
                                                new_rate, 
                                                before_time, 
                                                notify_time, 
                                                outage_time, 
                                                last_valid,
                                                after_time)

            self.test_cases.append(TestCase(video_url, 
                                            video_name, 
                                            abr, 
                                            search_method,
                                            network_conditions, 
                                            max_buffer,
                                            initial_quality,
                                            initial_buffer, 
                                            proto, 
                                            n))
            
            os.makedirs(self.results_dir, exist_ok=True)

    def run_iperf_tests(self):
        unique_net_profiles = [(test_case.net_condition, test_case.proto) for test_case in self.test_cases]
        iperf_result_dirname = os.path.join(self.results_dir, self.iperf_results_dir)
        os.makedirs(iperf_result_dirname, exist_ok=True)

        for (profile, proto) in unique_net_profiles:
            result = self.connectivity_test(profile, proto, interval=0.5)

            with open(os.path.join(iperf_result_dirname, profile.summarize()+proto), 'w+') as f:
                f.write(result[0])

    def connectivity_test(  self,
                            events: NetworkProfile,
                            proto: str,
                            interval=0.1,
                            iperf_port=DEFAULTS['iperf-port'], 
                            http_port=DEFAULTS['http-port'], 
                            cushion=DEFAULTS['cushion'],
                            quictun_client=DEFAULTS['quictun-client'],
                            quictun_server=DEFAULTS['quictun-server']
                            ) -> str:
        print('Started connectivity test')
        topo = SingleSwitchTopo(n=2)
        initial_rate = events.initial_rate

        intf = custom(TCIntf, bw=initial_rate)
        net = Mininet(topo, intf=intf)

        net.start()
        h1, h2 = net.get('h1', 'h2')
        link = net.linksBetween(h1, net.switches[0])[0]

        # Test link behavior using iperf
        h2.popen('iperf3 -s -p %d &' % iperf_port)

        if proto == 'quic':
            quictun_server_out = h2.popen(f'{quictun_server} --listen-on {h2.IP()}:7500 &')
            sleep(cushion)
            quictun_iperf_out = h1.popen(f'{quictun_client} --listen-on tcp:127.0.0.1:6501 --server-endpoint {h2.IP()}:7500 --token tcp:{h2.IP()}:{iperf_port} --insecure-skip-verify True &')
            sleep(cushion)
            print('started iperf quictun-client')

        iperf_time = events.get_duration()
        #print(iperf_time)

        if proto == 'quic':
            print('quic iperf')
            quic_iperf_client = h1.popen(f'iperf3 -c 127.0.0.1 -p 6501 -t {iperf_time} -f m -i {interval}')
        
        if proto == 'tcp':
            tcp_iperf_client = h1.popen(f'iperf3 -c {h2.IP()} -p {iperf_port} -t {iperf_time} -f m -i {interval}')

        rate_change_worker(events, link, h1)

        # Clean up
        if proto == 'quic':
            quic_iperf_out = [stream.decode('utf-8') for stream in quic_iperf_client.communicate()]
            print('QUIC iperf done')

        if proto == 'tcp':
            tcp_iperf_out = [stream.decode('utf-8') for stream in tcp_iperf_client.communicate()]
            print('TCP iperf done')

        sleep(cushion)

        h2.cmd('pkill iperf3')
        net.stop()

        if proto == 'tcp':
            return tcp_iperf_out
        else:
            return quic_iperf_out

    def run_tests(self):
        done = 0
        print(f'0 / {len(self.test_cases)}')
        for test_case in self.test_cases:
            # Set up output directory
            manifest = test_case.manifest()
            result_dirname = os.path.join(self.results_dir, str(test_case.uuid))
            #print(result_dirname)
            os.makedirs(result_dirname, exist_ok=True)

            # Run test
            header, results, logs = abr_test(test_case.net_condition.profile[0].new_rate, 
                                            test_case.net_condition, 
                                            test_case.video.url, 
                                            test_case.abr, 
                                            test_case.max_buffer, 
                                            test_case.search_method, 
                                            test_case.initial_quality, 
                                            test_case.initial_buffer, 
                                            test_case.proto)

            # Write results
            if self.write_headers:
                with open(os.path.join(result_dirname, 'header.txt'), 'w+') as header_file:
                    header_file.write(header)

            with open(os.path.join(result_dirname, 'results.json'), 'w+') as results_file:
                json.dump(results, results_file)

            if self.write_logs:
                with open(os.path.join(result_dirname, 'logs.txt'), 'w+') as log_file:
                    log_file.write(logs)
            
            with open(os.path.join(result_dirname, 'manifest.json'), 'w+') as manifest_file:
                json.dump(manifest, manifest_file)
            
            done += 1
            if done % self.update == 0:
                print(f'{done} / {len(self.test_cases)}')
    
class IStreamError(BaseException):
    pass

class SingleSwitchTopo(Topo):
    'Single switch connected to n hosts.'
    def build(self, n=2):
        switch = self.addSwitch('s1')
        # Python's range(N) generates 0..N-1
        for h in range(n):
            host = self.addHost('h%s' % (h + 1))
            self.addLink(host, switch)

def rate_change_worker(network_profile, link, client_host):
    #link.intf1.bwParamMax = 4000
    #print(f'modifiying link: {link}')
    def sleep_worker():
        notifier_bin = DEFAULTS['notifier']
        for event in network_profile.profile:
            if type(event) == RateChangeEvent:
                #print(f'rate change: {event.new_rate}, {event.duration}')
                link.intf1.config(bw=event.new_rate)
                sleep(event.duration)
            elif type(event) == NotifyEvent:
                #print(f'notification: -m {event.to_string()}')
                client_out = client_host.popen(f'{notifier_bin} -m {event.to_string()}')
                sleep(event.notification_time)
            elif type(event) == InactiveNotify:
                #print(f'notification: --{event.event_type}')
                client_out = client_host.popen(f'{notifier_bin} --{event.event_type}')
                
    thread = threading.Thread(target=sleep_worker)
    thread.start()

def connectivity_test(initial_rate: int,
                      events: NetworkProfile,
                      video: str, 
                      proto='TCP',
                      iperf_port=DEFAULTS['iperf-port'], 
                      http_port=DEFAULTS['http-port'], 
                      cushion=DEFAULTS['cushion'],
                      quictun_client=DEFAULTS['quictun-client'],
                      quictun_server=DEFAULTS['quictun-server']
                      ) -> tuple[str, str]:
    print('Started connectivity test')
    topo = SingleSwitchTopo(n=2)
    if initial_rate < 1000:
        intf = custom(TCIntf, bw=initial_rate)
    else:
        intf = custom(TCIntf, bw=1000)

    net = Mininet(topo, intf=intf)

    net.start()

    h1, h2 = net.get('h1', 'h2')

    link = net.linksBetween(h1, net.switches[0])[0]
    #link.intf1.bwParamMax = 4000
    link.intf1.config(bw=initial_rate)

    # Start QUICtun
    if proto == 'QUIC':
        print('quictun server')
        quictun_server_out = h2.popen(f'{quictun_server} --listen-on {h2.IP()}:7500 &')

    # Http-server
    server_out = h2.popen('http-server -p %d . &' % http_port)
    # Wait for the server to start
    sleep(cushion)

    # Test HTTP server using curl
    if proto == 'TCP':
        tcp_curl_client = h1.popen(f"curl -w '%{{speed_download}}' http://{h2.IP()}:{http_port}/{video}")
        tcp_curl_out = [stream.decode('utf-8') for stream in tcp_curl_client.communicate()]
        print('tcp curl done')

    if proto == 'QUIC':
        quictun_client_out = h1.popen(f'{quictun_client} --listen-on tcp:127.0.0.1:6500 --server-endpoint {h2.IP()}:7500 --token tcp:{h2.IP()}:{http_port} --insecure-skip-verify True &')
        sleep(cushion)
        #quictun_client_decode = [stream.decode('utf-8') for stream in quictun_client_out.communicate()]
        quic_curl_client = h1.popen('curl http://%s:%d/%s' % ('127.0.0.1', 6500, video))
        quic_curl_out = [stream.decode('utf-8') for stream in quic_curl_client.communicate()]
        # print(quic_curl_out)
        print('quic curl done')
    
    # Test link behavior using iperf
    h2.popen('iperf3 -s -p %d &' % iperf_port)
    print('started iperf')

    if proto == 'QUIC':
        quictun_iperf_out = h1.popen(f'{quictun_client} --listen-on tcp:127.0.0.1:6501 --server-endpoint {h2.IP()}:7500 --token tcp:{h2.IP()}:{iperf_port} --insecure-skip-verify True &')
        sleep(cushion)
        print('started iperf quictun-client')

    iperf_time = sum(map(get_event_duration, events)) + cushion
    #print(iperf_time)

    if proto == 'QUIC':
        quic_iperf_client = h1.popen(f'iperf3 -c 127.0.0.1 -p 6501 -t {iperf_time} -f m -i 0.1')
    
    if proto == 'TCP':
        tcp_iperf_client = h1.popen(f'iperf3 -c {h2.IP()} -p {iperf_port} -t {iperf_time} -f m -i 0.1')

    rate_change_worker(events, link, h1)

    # Clean up
    if proto == 'QUIC':
        quic_iperf_out = [stream.decode('utf-8') for stream in quic_iperf_client.communicate()]
        print('QUIC iperf done')

    if proto == 'TCP':
        tcp_iperf_out = [stream.decode('utf-8') for stream in tcp_iperf_client.communicate()]
        print('TCP iperf done')

    sleep(cushion)

    h2.cmd('pkill iperf3')
    net.stop()

    if proto == 'TCP':
        return tcp_curl_out, tcp_iperf_out
    else:
        return quic_curl_out, quic_iperf_out

def abr_test(initial_rate: int,
            events: list[tuple[int, float]], 
            video: str, 
            abr_strategy: str, 
            max_buffer: float,
            search_method: str,
            initial_quality: int | None,
            initial_buffer: float | None,
            proto: str,
            server_port=DEFAULTS['http-port'], 
            cushion=DEFAULTS['cushion'],
            istream=DEFAULTS['istream'],
            quictun_client=DEFAULTS['quictun-client'],
            quictun_server=DEFAULTS['quictun-server'],
            ) -> tuple[str, dict, str]:
    ''' Run a test involving a large bandwidth change. '''

    topo = SingleSwitchTopo(n=2)
    intf = custom(TCIntf, bw=1000)
    try:
        net = Mininet(topo, intf=intf)
    except:
        print('cleanup')
        cleanup()
        net = Mininet(topo, intf=intf)

    net.start()

    h1, h2 = net.get('h1', 'h2')

    link = net.linksBetween(h2, net.switches[0])[0]
    #link.intf1.bwParamMax = 4000
    link.intf1.config(bw=initial_rate)

    # Http-server
    if proto == 'QUIC':
        print('quictun')
        h2.popen(f'{quictun_server} --listen-on {h2.IP()}:7500 &')

    h2.popen('http-server -p %d . &' % server_port)

    #print('started server')
    # Wait for the server to start
    sleep(cushion)

    # Start iStream player
    if proto == 'QUIC':
        print('quictun')
        quictun_client_out = h1.popen(f'{quictun_client} --listen-on tcp:127.0.0.1:6500 --server-endpoint {h2.IP()}:7500 --token tcp:{h2.IP()}:{server_port} --insecure-skip-verify True &')
        sleep(cushion)
        if abr_strategy == 'fixed':
            istream_client = h1.popen(
                f'{istream} --mod_downloader tcp -i http://127.0.0.1:6500/{video} --mod_abr {abr_strategy} --initial_quality {initial_quality} --initial_buffer {initial_buffer} --max_buffer {max_buffer} --search_method {search_method}')
        else:
            istream_client = h1.popen(
                f'{istream} --mod_downloader tcp -i http://127.0.0.1:6500/{video} --mod_abr {abr_strategy} --max_buffer {max_buffer} --search_method {search_method}')
    else:
        if abr_strategy == 'fixed':
            istream_client = h1.popen(
                f'{istream} --mod_downloader tcp -i http://{h2.IP()}:{server_port}/{video} --mod_abr {abr_strategy} --initial_quality {initial_quality} --initial_buffer {initial_buffer} --max_buffer {max_buffer} --search_method {search_method}')
        else:
            print('tcp istream')
            istream_client = h1.popen(
                f'{istream} --mod_downloader tcp -i http://{h2.IP()}:{server_port}/{video} --mod_abr {abr_strategy} --max_buffer {max_buffer} --search_method {search_method}')

    print(f'istream started with {abr_strategy}')
    #print('started istream player')

    #sleep(cushion)
    #print('link:', link.intf1)
    rate_change_worker(events, link, h1)

    # Wait to avoid anything breaking
    #sleep(cushion)

    #print('await results')
    error_trace = istream_client.communicate()[1].decode('utf-8')
    results = istream_client.communicate()[0].decode('utf-8')

    #print('test finished')
    
    h2.popen('killall http-server')
    h1.popen('killall iplay')
    if proto == 'QUIC':
        h1.popen('killall quictun-client')
        h2.popen('killall quictun-server')
    
    #print('processes killed')
    net.stop()

    if len(results) == 0:
        return '', {}, error_trace
    else:
        split = results.partition('{')
        results_header = split[0]
        results_json = json.loads(split[1] + split[2])
        return results_header, results_json, error_trace

def mk_blockage(blockage,
                notification):
    ''' Returns a series of network events corresponding to a blockage. If a notification is specified,
        stitch that in there correctly.
    '''
    if blockage['outage_rate_multiplier'] == 0:
        rate_multiplier = 0.00000001
    else:
        rate_multiplier = blockage['outage_rate_multiplier']

    if notification is not None:
        return [('change', (blockage['rate1'], 
                            blockage['before_time'] - notification['notify_time'])), 

                ('start', None),

                ('notify', (blockage['rate1']*(1.0-notification['overhead1']), 
                            rate_multiplier * blockage['rate1'], 
                            blockage['rate2']*(1.0-notification['overhead2']), 
                            notification['notify_time'], 
                            blockage['outage_time'], 
                            notification['valid_time'])), 

                ('change', (blockage['rate1'], 
                            notification['notify_time'])), 

                ('change', (blockage['outage_rate_multiplier'] * blockage['rate1'],
                            blockage['outage_time'])), 
                
                ('stop', None),

                ('change', (blockage['rate2'], 
                            blockage['after_time'])),]

    else:
        return [('change', (blockage['rate1'], 
                            blockage['before_time'])), 

                ('start', None),
                ('change', (rate_multiplier * blockage['rate1'],
                            blockage['outage_time'])), 
                ('stop', None),

                ('change', (blockage['rate2'], 
                            blockage['after_time']))]

def get_event_duration(event):
    event_type, event_content = event
    if event_type == 'change':
        _, duration = event_content
        return duration
    elif event_type == 'notify':
        _, _, t1, t2, t3 = event_content
        return t1 + t2 + t3
    else:
        return 0.5

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mininet test suite for predictive ABR.')
    parser.add_argument('-v', '--video', action='store', type=str, nargs='+',
                        help='Relative URL of the MPD to fetch.', 
                        default=['videos/15s-test/multi_resolution.mpd'])
    parser.add_argument('-vn', '--video_names', action='store', type=str, nargs='+',
                        help='The names under which video results should be grouped in the results directory.',
                        default=None)
    parser.add_argument('-f', '--format', type=str, 
                        help='Format for video bitrate.', 
                        default=DEFAULTS['format'])
    parser.add_argument('-c', '--connectivity_test', action='store_true', 
                        help='Run a connectivity test (iperf+curl) and print the results, then exit.')
    parser.add_argument('--tcp', action='store_true',
                        help='Swap to TCP mode for connectivity tests.',
                        default=False)
    parser.add_argument('--both', action='store_true',
                        help='Perform both TCP and QUIC connectivity tests.',
                        default=False)
    parser.add_argument('--results', type=str, 
                        help='Directory to store results in. Should be empty.', 
                        default=DEFAULTS['results_dir'])
    parser.add_argument('--istream', type=str,
                        help='iStream Player client location.',
                        default=DEFAULTS['istream'])
    parser.add_argument('--quictunclient', type=str,
                        help='Quictun client location.',
                        default=DEFAULTS['quictun-client'])
    parser.add_argument('--quictunserver', type=str,
                        help='Quictun server location.',
                        default=DEFAULTS['quictun-server'])
    parser.add_argument('--debug', action='store_true', help='turns on spitting out curl output')
    args = parser.parse_args()

    if args.video_names is not None:
        videos: List[str] = zip(args.video, args.video_names)
    elif args.video is not None:
        video_names = map(lambda video_path: os.path.basename(os.path.dirname(video_path)), args.video)
        videos = list(zip(args.video, video_names))
    

    results_format: str = args.format
    test_first: bool = args.connectivity_test
    istream: str = args.istream
    results_dir: str = args.results 

    # Network test settings
    use_tcp: bool = args.tcp
    both: bool = args.both
    use_quic: bool = True
    if use_tcp and not both:
        use_quic = False
    debug = args.debug


    # Mininet log level
    setLogLevel('error')

    #buffer_level = TestDescription([], os.path.join(results_dir, 'delta_buffer'))

    #buffer_level.mk_test_cases(videos=videos, 
    #                    rates=[(300, 50, 50)],
    #                    durations=[(10, 2.0, 20)],
    #                    notify_times=[(3.0, 2.0)], 
    #                    abrs=['bandwidth'], 
    #                    search_methods=['none', 'greedy'], 
    #                    max_buffers=[1.5, 2.0, 2.5, 3.0], 
    #                    initial_qualities=[None], 
    #                    initial_buffers=[None], 
    #                    protos=['tcp', 'quic'], 
    #                    N=1)

    #buffer_level.write_logs = False
    #buffer_level.write_headers = False

    #print('init', len(buffer_level.test_cases))
    #buffer_level.run_tests()

    # buffer_level = TestDescription([], os.path.join(results_dir, 'delta_buffer2'))

    # buffer_level.mk_test_cases(videos=videos, 
    #                     rates=[(300, 50, 50)],
    #                     durations=[(10, 1.0, 20)],
    #                     notify_times=[(3.0, 2.0)], 
    #                     abrs=['lol', 'buffer'], 
    #                     search_methods=['none', 'greedy'], 
    #                     max_buffers=[2.0, 3.0, 4.0, 5.0], 
    #                     initial_qualities=[None], 
    #                     initial_buffers=[None], 
    #                     protos=['QUIC'], 
    #                     N=1)

    # buffer_level.write_logs = False
    # buffer_level.write_headers = False


    # 1, 2, 3, 4

    scen1 = TestDescription([], os.path.join(results_dir, 'pensieve-scen1'))

    scen1.mk_test_cases(videos=videos, 
                        rates=[(200, 50, 200)],
                        durations=[(10, 1.0, 20.0), (10, 1.0, 20.0), (10, 2.0, 20.0), (10, 3.0, 20.0), (10, 4.0, 20.0)],
                        notify_times=[(3.0, 6.0)], 
                        abrs=['pensieve'], 
                        search_methods=['none'], 
                        max_buffers=[3.0], 
                        initial_qualities=[None], 
                        initial_buffers=[None], 
                        protos=['tcp'], 
                        N=2)

    scen1.write_logs = False
    scen1.write_headers = False

    scen2 = TestDescription([], os.path.join(results_dir, 'pensieve-scen2'))

    scen2.mk_test_cases(videos=videos, 
                        rates=[(200, 50, 50)],
                        durations=[(10, 1.0, 20.0), (10, 2.0, 20.0), (10, 3.0, 20.0), (10, 4.0, 20.0)],
                        notify_times=[(3.0, 6.0)], 
                        abrs=['pensieve'], 
                        search_methods=['none'], 
                        max_buffers=[3.0], 
                        initial_qualities=[None], 
                        initial_buffers=[None], 
                        protos=['tcp'], 
                        N=2)

    scen2.write_logs = False
    scen2.write_headers = False

    scen1.run_tests()
    scen2.run_tests()
