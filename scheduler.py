'''
    This script is used to invoke the emulator. It changes a lot. Since this file is constantly used
    to actually invoke tests, it serves as a good set of examples on how to use the underlying library.
'''

import argparse
import os
import uuid

from typing import List, Tuple, Any
from copy import deepcopy

from abr_emulator import scheduler
from abr_emulator import networking

parser = argparse.ArgumentParser(description='Mininet test suite for predictive ABR.')
parser.add_argument('-v', '--video', action='store', type=str, nargs='+',
                    help='Relative URL of the MPD to fetch.', 
                    default=['videos/15s-test/multi_resolution.mpd'])
parser.add_argument('-vn', '--video_names', action='store', type=str, nargs='+',
                    help='The names under which video results should be grouped in the results directory.',
                    default=None)
parser.add_argument('-p', '--pure', 
                    help='Perform a "dry run", i.e. construct all relevant tests, print info about them, and exit.',
                    action='store_true')
parser.add_argument('-s', '--num_servers', type=int,
                    help='How many virtual servers to use.',
                    default=1)
parser.add_argument('-c', '--num_clients', type=int,
                    help='How many virtual servers to use.',
                    default=50)
parser.add_argument('--run_errors',
                    help='Runs tests including errors in prediction time and action taken.',
                    action='store_true')
args = parser.parse_args()

if args.video_names is not None:
    videos: List[Tuple[str, str]] = list(zip(args.video, args.video_names))
elif args.video is not None:
    video_names = map(lambda video_path: os.path.basename(os.path.dirname(video_path)), args.video)
    videos: List[Tuple[str, str]] = list(zip(args.video, video_names))
else:
    print('Wrong video arguments')
    exit(1)

num_clients = args.num_clients
num_servers = args.num_servers

# Run normal tests
tests = scheduler.TestDescription([], 'results/nontransient-force-lowest')
tests.init()

short_errors = [(0, 0, 0)]

tests.mk_test_cases(videos=videos, 
                    rates=[(300, 10, 10)],
                    durations=[(10, 0, 30)],
                    notify_times=[(3.0, 6.0)], 
                    notify_errors=short_errors,
                    abrs=['bandwidth', 'buffer', 'lol'],
                    #abrs=['bandwidth'],
                    search_methods=['none'],
                    max_buffers=[2.0, 3.0, 5.0, 10.0], 
                    initial_qualities=[None], 
                    initial_buffers=[None], 
                    use_quic=[False],
                    N=4)

# Exit if we don't need to do a full run
if args.pure:
    print(f'Number of tests: {tests.num_tests()}')
    exit(0)

print(f'Running {tests.num_tests()} using {num_servers} servers and {num_clients} clients')

tests.start_net(num_servers=num_servers, num_clients=num_clients)
results = tests.run_tests(write_headers=False,write_errors=False)
print(f'Successfully completed {len(results)}/{tests.num_tests()} tests.')

if not args.run_errors:
    tests.stop_net()
    exit(0)

# Now add errors
#errors = [(x, 0, 0) for x in range(-2, 3)] + [(0, 0, x) for x in range(-50, 60, 25)]
errors = [(x, 0, 0) for x in range(-2, 3)] + [(0, 0, x) for x in range(-50, 60, 25)]

tests.test_cases = []

for (test, result) in results:
    if test.search_method == 'greedy':
        plan = result['plans'][0]
        plan = [d['0'] for d in plan]
        #print(plan)

        for error in errors:
            new_test = deepcopy(test)
            new_test.uuid = uuid.uuid4()

            t1, t2, rd = error
            new_test.search_method = 'greedy'
            network_condition = networking.NetworkProfile(test.net_condition.initial_rate, 
                                                        test.net_condition.outage_rate, 
                                                        test.net_condition.new_rate, 
                                                        test.net_condition.before_time, 
                                                        test.net_condition.notify_time, 
                                                        test.net_condition.outage_time, 
                                                        test.net_condition.valid, 
                                                        test.net_condition.after_time,
                                                        (t1, t2, rd),
                                                        None)
            new_test.net_condition = network_condition

            tests.test_cases.append(new_test)

with_errors = tests.run_tests(write_headers=False, write_errors=False)

tests.stop_net()

print('done')