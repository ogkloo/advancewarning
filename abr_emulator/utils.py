from itertools import islice, chain
from threading import Thread
from typing import Generator, Iterable, List, Any

import abr_emulator.networking as network

def chunks(l: Iterable[Any], n: int) -> Generator:
    """Yield n number of striped chunks from l."""
    for i in range(0, n):
        yield l[i::n]

def batched(iterable: Iterable[Any], n: int) -> Generator[tuple, Any, None]:
    "Batch data into tuples of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch

def playback_wrapper(link, network_profiles) -> Thread:
    # Starts a worker thread which plays back a network profile list
    def worker():
        network.playback(link, network_profiles)

    thread = Thread(target=worker)
    return thread

def flatten(xs: Iterable[Any]) -> List[Any]:
    return list(chain(*xs))

def single_threaded_playback_wrapper(streams) -> Thread:
    # Starts a worker thread which plays back a network profile list
    def worker():
        network.single_thread_playback(streams)

    thread = Thread(target=worker)
    return thread