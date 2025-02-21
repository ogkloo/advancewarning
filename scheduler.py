import argparse
import os
import itertools

from typing import List

from abr_emulator import scheduler
from abr_emulator import networking

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

# Run normal tests
tests = scheduler.TestDescription([], 'results/results-accuracy')

short_errors = [(0, 0, 0)]

tests.mk_test_cases(videos=videos, 
                    rates=[(300, 50, 300), 
                           (300, 50, 50)],
                    durations=[(10, 1.0, 20.0), 
                               (10, 2.0, 20.0), 
                               (10, 3.0, 20.0)],
                    notify_times=[(3.0, 6.0)], 
                    notify_errors=short_errors,
                    abrs=['bandwidth'],
                    search_methods=['none', 
                                    'greedy'], 
                    max_buffers=[3.0], 
                    initial_qualities=[None], 
                    initial_buffers=[None], 
                    use_quic=[False],
                    N=1)

print(f'Running {tests.num_tests()}')

results = tests.run_tests(num_servers=1,
                          num_clients=50,
                          write_headers=False,
                          write_errors=False)

print('done with testset 1')

# Now add errors
errors = [(x, 0, 0) for x in range(-2, 3)] + [(0, 0, x) for x in range(-50, 60, 25)]

new_tests = scheduler.TestDescription([], 'results/results-accuracy')

for (test, result), (t1, t2, rd) in itertools.product(results, errors):
    if test.search_method == 'greedy':
        plan = result['plans'][0]
        plan = [d['0'] for d in plan]
        print(plan)

        test.search_method = 'explicit'
        test.start_error = t1
        test.end_error = t2
        test.rate_error = rd
        network_condition = networking.NetworkProfile(test.net_condition.initial_rate, 
                                                       test.net_condition.outage_rate, 
                                                       test.net_condition.new_rate, 
                                                       test.net_condition.before_time, 
                                                       test.net_condition.notify_time, 
                                                       test.net_condition.outage_time, 
                                                       test.net_condition.valid, 
                                                       test.net_condition.after_time,
                                                       (t1, t2, rd),
                                                       plan)
        test.net_condition = network_condition

        new_tests.test_cases.append(test)

with_errors = new_tests.run_tests(num_servers=1,
                                  num_clients=50, 
                                  write_headers=False, 
                                  write_errors=False)

print('done')