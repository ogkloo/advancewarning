import threading
from typing import List

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCIntf
from mininet.util import custom

from dataclasses import dataclass
from time import sleep

from .config import DEFAULTS

@dataclass
class RateChangeEvent():
    ''' Describes a rate and a duration.

    Constructor usage: RateChangeEvent(new_rate, duration)
    '''
    new_rate: float
    duration: float

@dataclass
class NotifyEvent():
    notification_time: float
    outage_duration: float
    last_valid: float

    start_rate: float
    outage_rate: float
    end_rate: float

    def to_string(self):
        return f'{self.start_rate},{self.outage_rate},{self.end_rate},{self.notification_time},{self.outage_duration},{self.last_valid}'

@dataclass
class InactiveNotify():
    event_type: 'str'

class NetworkProfile():
    def __init__(self, 
                 initial_rate, 
                 outage_rate, 
                 new_rate, 
                 before_time, 
                 notify_time, 
                 outage_time, 
                 valid_time, 
                 after_time):

        self.summary = f'{initial_rate}, {outage_rate}, {new_rate}, {before_time}, {notify_time}, {outage_time}, {valid_time}, {after_time}'

        self.initial_rate = initial_rate
        self.outage_rate = outage_rate
        self.new_rate = new_rate
        self.before_time = before_time
        self.notify_time = notify_time
        self.outage_time = outage_time
        self.valid = valid_time
        self.after_time = after_time

        self.profile = [RateChangeEvent(initial_rate, 
                                        before_time-notify_time), 
                        NotifyEvent(notify_time, 
                                    outage_time, 
                                    valid_time, 
                                    initial_rate, 
                                    outage_rate, 
                                    new_rate),
                        RateChangeEvent(initial_rate, 
                                        notify_time),
                        RateChangeEvent(outage_rate, 
                                        outage_time), 
                        InactiveNotify('stop'),
                        RateChangeEvent(new_rate, 
                                        after_time)]
    
    def summarize(self):
        return self.summary

    def get_duration(self):
        return self.before_time + self.outage_time + self.after_time
    
    def to_json(self):
        return {
            'initial_rate': self.initial_rate,
            'outage_rate': self.outage_rate,
            'new_rate': self.new_rate,
            'before_time': self.before_time,
            'notify_time': self.notify_time,
            'outage_time': self.outage_time,
            'valid': self.valid,
            'after_time': self.after_time
        }

class SingleSwitchTopo(Topo):
    'Single switch connected to n hosts.'
    def build(self, n=2):
        switch = self.addSwitch('s1')
        # Python's range(N) generates 0..N-1
        for h in range(n):
            host = self.addHost('h%s' % (h + 1))
            self.addLink(host, switch)

''' TODO: Really, the design here should be much better.
    This topology could be better understood as one of a few things:

    1. A set of switches, each connecting _n_ disjoint sets of hosts. 
    2. _n_ disjoint sets of hosts, with each host in a host set being connected 
       to the same set of switches.

    In either case, the size of the host sets are unconstrained and may vary
    freely. The switch topology could also vary freely, although the 
    construction could more or less assume that they were unconnected, or that
    their interconnection didn't matter very much.

    For now, what's going on here is that a domain is a single switch with 2
    disjoint sets, called clients and servers. This is still advantageous so
    I'm keeping it for now. But this note will hopefully remind me to get back
    to it, since a much more general, richer topology which represents quite a
    lot of real-world networks is possible.
'''
class NetworkDomain():
    def __init__(self, switch, servers, clients):
        self.switch = switch
        self.servers = servers
        self.clients = clients

class MultiSwitchServerClient(Topo):
    '''
        2 disjoint sets of machines per switch
    '''
    def __init__(self, domains):
        super().__init__()
        self.domains = []

        # Each domain contains a list of pairs of (num_servers, num_clients)
        for i in range(len(domains)):
            num_servers, num_clients = domains[i]
            switch = self.addSwitch(f'switch-{i}')

            servers = []
            for server_number in range(num_servers):
                server = self.addHost(f'server-{server_number}')
                self.addLink(server, switch)
                servers.append(server)

            clients = []
            for client_number in range(num_clients):
                client = self.addHost(f'client-{client_number}')
                self.addLink(client, switch)
                clients.append(client)
            
            domain = NetworkDomain(switch, servers, clients)
            self.domains.append(domain)

class NetCommander(Mininet):
    '''
        A mininet net with initial rates and two disjoint sets of hosts per domain.
    '''
    def __init__(self, topo: MultiSwitchServerClient):
        intf = custom(TCIntf)
        super().__init__(topo, intf=intf)

    def start(self, 
              per_domain_server_limits,
              per_domain_client_limits):

        super().start()

        for (domain, server_limits, client_limits) in zip(self.topo.domains, 
                                                          per_domain_server_limits, 
                                                          per_domain_client_limits):
            
            switch = self.get(domain.switch)

            # Links between servers and switch in domain
            for server, limits in zip(domain.servers, server_limits):
                up_limit, down_limit = limits
                net_server = self.get(server)
                links = self.linksBetween(net_server, switch)
                for link in links:
                    link.intf1.config(bw=up_limit)
                    link.intf2.config(bw=down_limit)

            for client, limits in zip(domain.clients, client_limits):
                up_limit, down_limit = limits
                net_client = self.get(client)
                links = self.linksBetween(net_client, switch)
                for link in links:
                    link.intf1.config(bw=up_limit)
                    link.intf2.config(bw=down_limit)
            
    def clients(self):
        domains = self.topo.domains
        clients = []
        for domain in domains:
            clients += domain.clients
        
        return map(self.get, clients)

    def servers(self):
        domains = self.topo.domains
        servers = []
        for domain in domains:
            servers += domain.servers
        
        return map(self.get, servers)
    
    def client_links(self):
        '''
            Return all links between clients and switches across all domains.
        '''
        # TODO: Filter by domain?
        domains = self.topo.domains
        links = []
        for domain in domains:
            for client in domain.clients:
                links += self.linksBetween(self.get(client), 
                                           self.get(domain.switch))

        return links

    def server_links(self):
        '''
            Return all links between servers and switches across all domains.
        '''
        # TODO: Filter by domain?
        domains = self.topo.domains
        links = []
        for domain in domains:
            for server in domain.servers:
                links += self.linksBetween(self.get(server), 
                                           self.get(domain.switch))

        return links
    
def playback(link, network_profiles: List[RateChangeEvent], uplink=False):
    '''
        'Play' a profile from a list of profiles `network_profiles` for a 
        given link `link`.

        By default, controls the host's *downlink* speed as set by TC. To set 
        uplink speed, set the uplink argument to true.
    '''
    # TODO: Find some sane way to make this async when you go and do that.
    # Really, this should properly send asyncio events or something.
    # Currently, it's just gonna run and I hope you put it on another thread.

    for profile in network_profiles:
        link.intf2.config(bw=profile.new_rate)
        sleep(profile.duration)