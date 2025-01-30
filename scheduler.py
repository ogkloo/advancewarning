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

tests = scheduler.TestDescription([], 'tests/results')

tests.mk_test_cases(videos=videos, 
                    rates=[(200, 50, 200)],
                    durations=[(10, 1.0, 20.0), 
                               (10, 1.0, 20.0), 
                               (10, 2.0, 20.0), 
                               (10, 3.0, 20.0), 
                               (10, 4.0, 20.0)],
                    notify_times=[(3.0, 6.0)], 
                    abrs=['bandwidth'], 
                    search_methods=['none'], 
                    max_buffers=[3.0], 
                    initial_qualities=[None], 
                    initial_buffers=[None], 
                    use_quic = [False],
                    N=1)

tests.run_tests(1, 5)