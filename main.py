from concurrent.futures import ThreadPoolExecutor
from prometheus_client import start_http_server, Gauge
import prometheus_client
import re, socket, time, os, dns.resolver
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


def find_files():
    files = []
    upstream_files = []
    for dirpath, dirs, found_files in os.walk('/home/alex/ansible-playbooks/roles/nginx-balancer/files/nginx'):
        for filename in found_files:
            fname = os.path.join(dirpath,filename)
            files.append(fname)
    for i in files:
        with open(i, 'r') as f:
            content = f.read()
            if 'upstream upstream_' in content:
                upstream_files.append(i)
    return upstream_files


def parse_nginx_configs(files):
    upstreams = []
    for file in files:
        with open(file, 'r') as f:
            lines = f.readlines()
            upstream_name = None
            for line in lines:
                if 'upstream upstream_' in line:
                    capture = re.search('^upstream upstream_(.*) {', line)
                    upstream_name = capture.group(1)
                elif re.search('server (\w.*):(\d+)(.*|;)', line) is not None and 'down' not in line:
                    match_obj = re.search('server (\w.*):(\d+)(.*|;)', line)
                    address = match_obj[1]
                    port = match_obj[2]
                    upstream_type = 'backup' if 'backup' in match_obj[3] else 'primary'
                    upstreams.append((upstream_name, address, port, upstream_type))
    return upstreams


def check_port(i):
    upstream_name, address, port, upstream_type = i[0], i[1], int(i[2]), i[3]
    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            ip = str(dns.resolver.resolve(address, 'A')[0])
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
    update_delay = 30
    metric.clear()
    while True:
        if len(futures) > 0:
            for task in futures:
                if task.done():
                    print(f'remove: {task}')
                    futures.remove(task)
        with ThreadPoolExecutor(4) as executor:
            futures = [executor.submit(check_port, i) for i in upstreams]
        time.sleep(100)
        update_delay -= 10
        if update_delay == 0:
            break


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(9900)

    while True:
        files = find_files()
        upstreams = parse_nginx_configs(files)
        update_metrics(upstreams)
