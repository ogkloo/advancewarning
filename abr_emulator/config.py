from dataclasses import dataclass
from enum import Enum

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

class Format(Enum):
    # All formats in base 10 rather than base 2, 1kbit = 1000bits
    BITS = 0
    KBITS = 1
    MBITS = 2
    GBITS = 3

    BYTES = 4
    KBYTES = 5
    MBYTES = 6
    GBYTES = 7

@dataclass
class Config():
    # Format for results. Ex. Format.b for bits.
    format: Format
    
    # Paths?
    # Where to find binaries.
    istream_bin: str 
    notifier_bin: str 
    quictun_client_bin: str 
    quictun_server_bin: str

    # Ports for istream and the http-server.
    iperf_port: int
    http_port: int

    # How long to sleep in seconds in between certain operations.
    cushion: int

    # tmpdir stores mostly istream tests. Should be empty most of the time.
    tmpdir: str

    # Top level results directory for video streaming tests.
    results_dir: str
    # Top level results directory for iperf tests.
    connectivity_results_dir: str

    @classmethod
    def defaults(cls):
        '''
            Roughly equivalent to DEFAULTS rn
        '''
        return cls(format=Format.MBYTES,
                   istream_bin='../istream-player/istream',
                   notifier_bin='../istream-player/send_event.sh',
                   quictun_client_bin='../quictun/quictun-client',
                   quictun_server_bin='../quictun/quictun-server',
                   iperf_port=5001,
                   http_port=8080,
                   cushion=2,
                   tmpdir='../tmp',
                   results_dir='../results/main',
                   connectivity_results_dir='..results/connectivity')

default_config = Config.defaults()