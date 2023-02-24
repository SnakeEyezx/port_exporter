from prometheus_client import start_http_server, Gauge
import socket
import time

_hostname = 'this_hostname'
_hosts = {
'host01':'192.168.100.1',
'host02':'192.168.100.2',
'host03':'192.168.100.3'
}
_ports = (8010, 8020, 8030)

def create_obj():
    objs = list()
    for k,v in _hosts.items():
        for p in _ports:
            print(k,p)
            objs.append(Gauge(f"{_hostname}__{k}:{p}__stackname", "Some_metric"))
    return objs

_objs = create_obj()

def get_metric(_target, _port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    result = sock.connect_ex((_target, _port))
    print(result)
    x = 0
    if result == 0:
        x = 0
    else:
        x = 1
    sock.close()
    return (x)

def collect_metrics():
    i = 0
    for k,v in _hosts.items():
        for p in _ports:
            _value = get_metric(v,p)
            _objs[i].set(_value)
            i += 1

if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(8100)

    while True:
        collect_metrics()
        time.sleep(10)
