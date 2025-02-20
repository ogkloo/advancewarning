import argparse
import os
from typing import List

from abr_emulator import scheduler

parser = argparse.ArgumentParser(description='Mininet test suite for predictive ABR.')
parser.add_argument('-v', '--video', action='store', type=str, nargs='+',
                    help='Relative URL of the MPD to fetch.', 
                    default=['videos/15s-test/multi_resolution.mpd'])
parser.add_argument('-vn', '--video_names', action='store', type=str, nargs='+',
                    help='The names under which video results should be grouped in the results directory.',
                    default=None)
args = parser.parse_args()

if args.video_names is not None:
    videos: List[str] = zip(args.video, args.video_names)
elif args.video is not None:
    video_names = map(lambda video_path: os.path.basename(os.path.dirname(video_path)), args.video)
    videos = list(zip(args.video, video_names))

tests = scheduler.TestDescription([], 'results/results-accuracy')

errors = [(x, 0, 0) for x in range(-2, 3)] + [(0, 0, x) for x in range(-50, 60, 25)]
short_errors = [(x, 0, 0) for x in [-1, 0, 1]]

tests.mk_test_cases(videos=videos, 
                    rates=[(200, 50, 200), 
                           (200, 50, 50)],
                    durations=[(10, 1.0, 20.0), 
                               (10, 2.0, 20.0), 
                               (10, 3.0, 20.0)],
                    notify_times=[(3.0, 6.0)], 
                    notify_errors=errors,
                    abrs=['bandwidth', 
                          'buffer', 
                          'lol'], 
                    search_methods=['none', 
                                    'greedy'], 
                    max_buffers=[3.0], 
                    initial_qualities=[None], 
                    initial_buffers=[None], 
                    use_quic=[False],
                    N=2)

print(f'Running {tests.num_tests()}')

tests.run_tests(num_servers=1,
                num_clients=50,
                write_headers=False,
                write_errors=False)