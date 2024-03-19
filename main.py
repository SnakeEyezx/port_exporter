from concurrent.futures import ThreadPoolExecutor
from prometheus_client import start_http_server, Gauge
import prometheus_client
import re, socket, time, os, dns.resolver, ipaddress, crossplane
from socket import AF_INET
from socket import SOCK_STREAM
from socket import socket


prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)

hostname = os.uname() or 'default'

metric = Gauge('port_is_not_open',
                'Check_port_metric',
                ['hostname','target', 'port', 'name', 'upstream_type'])


def get_upstreams():
    payload = crossplane.parse('/etc/nginx/nginx.conf')
    ustream_configs = []
    upstreams = []

    for i in payload['config']:
        if 'upstream' in [d.get('directive') for d in i['parsed']]:
            ustream_configs.append(i['parsed'])

    for i in ustream_configs:
        for d in i:
            if d['directive'] == 'upstream':
                upstream_name = d['args'][0]
                for h in d['block']:
                    if h['directive'] == 'server' and 'down' not in h['args']:
                        if ':' in h['args'][0]:
                            address, port = h['args'][0].split(':')
                        else:
                            address = h['args'][0]
                            port = '80'
                        upstream_type = 'backup' if 'backup' in h['args'] else 'primary'
                        upstreams.append((upstream_name, address, port, upstream_type))
    return upstreams



def check_upstream(i):
    upstream_name, address, port, upstream_type = i[0], i[1], int(i[2]), i[3]
    try:
        a = ipaddress.ip_address(address)
    except ValueError:
        ip = str(dns.resolver.resolve(address, 'A')[0])
    else:
        ip = address
    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            result = sock.connect_ex((ip, port))
        except Exception as e:
            # log = 'logging error'
            pass
        else:
            metric_value = 0 if result == 0 else port
            metric.labels(hostname.nodename,
                            address,
                            port,
                            upstream_name,
                            upstream_type).set(metric_value)


def update_metrics(upstreams):
    futures = []
    reload_delay = 30
    metric.clear()
    while True:
        if len(futures) > 0:
            for task in futures:
                if task.done():
                    futures.remove(task)
        with ThreadPoolExecutor(4) as executor:
            futures = [executor.submit(check_upstream, i) for i in upstreams]
        time.sleep(5)
        reload_delay -= 5
        if reload_delay == 0:
            break


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(9900)

    while True:
        upstreams = get_upstreams()
        update_metrics(upstreams)
