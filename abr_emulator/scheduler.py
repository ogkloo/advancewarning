import uuid
import itertools
import os
import json

from dataclasses import dataclass
from time import sleep
from typing import List

from mininet.clean import cleanup
from mininet.net import Mininet
from mininet.link import TCIntf
from mininet.util import custom

from .config import DEFAULTS
from .networking import (RateChangeEvent, 
                         NotifyEvent, 
                         InactiveNotify, 
                         NetworkProfile, 
                         SingleSwitchTopo)

def rate_change_worker(a, b, c):
    ''' rate_change_worker 
        Originally, this method changed the link rate according to a schedule, 
        however this usage is deprecated as part of the move to a more 
        principled way of managing the link rate schedule process.

    Args:
        a (_type_): Deprecated.
        b (_type_): Deprecated.
        c (_type_): Deprecated.

    Raises:
        AssertionError: Always raised, method unimplemented.
    '''

    # TODO: Remove this definition entirely.
    raise AssertionError('This method is deprecated and calls to it must be removed')

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

    def __init__(self, 
                 video_mpd, 
                 video_name, 
                 abr, 
                 search_method, 
                 net_condition, 
                 max_buffer, 
                 initial_quality, 
                 initial_buffer, 
                 proto, 
                 n):

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