from typing import List

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCIntf
from mininet.util import custom

from dataclasses import dataclass
from time import sleep

import abr_emulator.utils as utils

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
                 after_time,
                 error_trio=None):

        self.initial_rate = initial_rate
        self.outage_rate = outage_rate
        self.new_rate = new_rate
        self.before_time = before_time
        self.notify_time = notify_time
        self.outage_time = outage_time
        self.valid = valid_time
        self.after_time = after_time

        if error_trio is not None:
            start_error, end_error, rate_error = error_trio

            self.start_error = start_error
            self.end_error = end_error
            self.rate_error = rate_error
        else:
            self.start_error = 0
            self.end_error = 0 
            self.rate_error = 0 

        self.summary = f'{initial_rate}, {outage_rate}, {new_rate}, {before_time}, {notify_time}, {outage_time}, {valid_time}, {after_time}, {self.start_error}, {self.end_error}, {self.rate_error}'

        self.profile = [RateChangeEvent(initial_rate, 
                                        before_time-notify_time), 
                        NotifyEvent(notify_time + self.start_error, 
                                    outage_time + self.end_error, 
                                    valid_time, 
                                    initial_rate, 
                                    outage_rate + self.rate_error, 
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
            'after_time': self.after_time,
            'start_error': self.start_error,
            'end_error': self.end_error,
            'rate_error': self.rate_error
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
    
    def links_on_client(self):
        '''
            This is very similar to the above method but also includes which 
            client is involved.
        '''
        domains = self.topo.domains
        links = {}
        for domain in domains:
            for client in domain.clients:
                links[self.get(client)] = self.linksBetween(self.get(client), 
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

        TC is actually too slow most of the time.
    '''
    # TODO: Find some sane way to make this async when you go and do that.
    # Really, this should properly send asyncio events or something.
    # Currently, it's just gonna run and I hope you put it on another thread.
    for profile in network_profiles:
        if type(profile) == RateChangeEvent:
            link.intf2.config(bw=profile.new_rate)
            sleep(profile.duration)

class NetEvent2():
    # Need to think about this constructor
    def __init__(self, link, client, port, rate, time, type=0, subevent=None):
        self.link = link
        self.client = client
        self.port = port
        self.rate = rate
        self.time = time

        # 0 == rate change
        # 1 == notify
        # 2 == inactive
        self.type = type
        self.subevent: NotifyEvent | InactiveNotify | None = subevent

def absolute_time_profile(link, client, port, profile):
    # Make the profile start at 0 + append the link to it
    t = 0
    out = []

    for event in profile:
        if type(event) == RateChangeEvent:
            out.append(NetEvent2(link, client, port, event.new_rate, 
                                 event.duration + t, 
                                 type = 0, subevent = event))
            t += event.duration

        elif type(event) == NotifyEvent:
            out.append(NetEvent2(link, client, port, event.start_rate, 
                                 event.notification_time + t, 
                                 type = 1, subevent = event))
            t += event.notification_time

        elif type(event) == InactiveNotify:
            out.append(NetEvent2(link, client, port, 0, t, 
                                 type = 2, subevent = event))

    return out

def unify_streams(streams):
    # Streams are pairs of (link, profile_list)
    a = [absolute_time_profile(link, client, port, test_case.net_condition.profile) 
         for link, client, port, test_case in streams]

    # Get flattened list of NetEvent2s
    af = utils.flatten(a)

    # Sort by occurrence time
    return sorted(af, key=lambda e: e.time)

def single_thread_playback(streams):
    events = unify_streams(streams)

    now = 0
    for event in events:
        if event.type == 0:
            sleep(event.time - now)
            event.link.intf2.config(bw=event.rate)
            now = event.time

        elif event.type == 1:
            sleep(event.time - now)
            send = event.client.popen(["nix-shell", "--run", 
                                       f"./istream-player/send_event.sh -p {event.port} -m {event.subevent.to_string()}"])
            # print([stream.decode('utf-8') for stream in send.communicate()])
            now = event.time

        elif event.type == 2:
            send = event.client.popen(["nix-shell", "--run", 
                                       f"./istream-player/send_event.sh -p {event.port} --{event.subevent.event_type}"])
            # print([stream.decode('utf-8') for stream in send.communicate()])