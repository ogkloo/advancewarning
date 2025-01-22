import argparse
import os

from typing import List
from mininet.log import setLogLevel

from config import DEFAULTS
from scheduler import TestDescription

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

    scen2 = TestDescription([], os.path.join(results_dir, '600scen2-batch2'))

    scen2.mk_test_cases(videos=videos, 
                        rates=[(500, 50, 50)],
                        durations=[(10, 1.0, 20.0), (10, 2.0, 20.0), (10, 3.0, 20.0), (10, 4.0, 20.0)],
                        notify_times=[(3.0, 6.0)], 
                        abrs=['bandwidth', 'lol', 'buffer'], 
                        search_methods=['none', 'greedy'], 
                        max_buffers=[3.0], 
                        initial_qualities=[None], 
                        initial_buffers=[None], 
                        protos=['tcp'], 
                        N=1)

    scen2.write_logs = False
    scen2.write_headers = False

    scen2.run_tests()
