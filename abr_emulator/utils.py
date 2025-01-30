from itertools import islice, chain
from threading import Thread

import abr_emulator.networking as network

def chunks(l, n):
    """Yield n number of striped chunks from l."""
    for i in range(0, n):
        yield l[i::n]

def batched(iterable, n):
    "Batch data into tuples of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch

def playback_wrapper(link, network_profiles):
    # Starts a worker thread which plays back a network profile list
    def worker():
        network.playback(link, network_profiles)

    thread = Thread(target=worker)
    return thread

def flatten(xs):
    return list(chain(*xs))

def single_threaded_playback_wrapper(streams):
    # Starts a worker thread which plays back a network profile list
    def worker():
        network.single_thread_playback(streams)

    thread = Thread(target=worker)
    return thread