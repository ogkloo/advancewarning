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
from .networking import *
from .utils import *


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

    # These rarely need to be set
    server_port = 8080
    istream = DEFAULTS['istream']
    quictun_client = DEFAULTS['quictun-client']

    def __init__(self, 
                 video_mpd, 
                 video_name, 
                 abr, 
                 search_method, 
                 net_condition, 
                 max_buffer, 
                 initial_quality, 
                 initial_buffer, 
                 use_quic, 
                 n):

        self.uuid = uuid.uuid4()

        self.video = self.Video(video_name, video_mpd)
        self.abr = abr
        self.search_method = search_method
        self.net_condition = net_condition
        self.max_buffer = max_buffer
        self.initial_quality = initial_quality
        self.initial_buffer = initial_buffer
        self.use_quic = use_quic 
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
                'use_quic': self.use_quic,
                'n': self.n,
                'server_port': self.server_port,
                'istream': self.istream}
    
    def run_test(self, server_host, client_host):
        '''Run this test between an already running server_host and new client_host.

        Args:
            server_host (`Mininet.Host`): A host which should be already running an http server.
            client_host (`Mininet.Host`): The host to run the test on.
        '''        
        server_ip = server_host.IP()
        if not self.use_quic:
            istream_client = client_host.popen(
                f'{self.istream} --mod_downloader tcp -i http://{server_ip}:{self.server_port}/{self.video.url} --mod_abr {self.abr} --max_buffer {self.max_buffer} --search_method {self.search_method}')
        else:
            quictun_client_out = client_host.popen(
                f'{self.quictun_client} --listen-on tcp:127.0.0.1:6500 --server-endpoint {server_ip}:7500 --token tcp:{server_ip}:{self.server_port} --insecure-skip-verify True &')
            istream_client = client_host.popen(
                f'{self.istream} --mod_downloader tcp -i http://127.0.0.1:6500/{self.video.url} --mod_abr {self.abr} --max_buffer {self.max_buffer} --search_method {self.search_method}')
        
        return istream_client

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
                      use_quic, 
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
                                      use_quic,
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

    def run_tests(self, num_servers, num_clients):
        # Just put them all on one domain rn
        domains = [(num_servers, num_clients)]
        topo = MultiSwitchServerClient(domains)
        net = NetCommander(topo)
        net.start([[(5000, 1000)]*num_servers], [[(250, 250)]*num_clients])

        client_server_map = {}
        for (server, clients) in zip(net.servers(), 
                                     chunks(list(net.clients()), num_servers)):
            client_server_map = {**client_server_map, **{client: server for client in clients}}

        server_processes = [server.popen('http-server -p %d . &' % 8080) for server in net.servers()]
        sleep(2)

        done = 0
        print(f'0 / {len(self.test_cases)}')

        batches = chunks(self.test_cases, num_clients)
        print(batches)
        for batch in batches:
            # Set up output directory
            for test_case in batch:
                manifest = test_case.manifest()
                result_filename = os.path.join(self.results_dir, str(test_case.uuid) + '.json')
            
            istream_out = [test_case.run_test(client_server_map[client], client) 
                           for test_case, client in zip(batch, net.clients())]

            streams = [result.communicate() for result in istream_out]
            results = [stream[0].decode('utf-8') for stream in streams]
            errors = [stream[1].decode('utf-8') for stream in streams]

            for result in results:
                if len(result) != 0:
                    split = result.partition('{')
                    results_header = split[0]
                    results_json = json.loads(split[1] + split[2])

                with open(result_filename, 'w+') as results_file:
                    json.dump(results_json, results_file)

            done += len(batch)
            if done % self.update == 0:
                print(f'{done} / {len(self.test_cases)}')
        
        net.stop()