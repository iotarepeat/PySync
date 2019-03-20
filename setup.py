import json
import socket
from hashlib import sha1
from multiprocessing.pool import ThreadPool

THREAD_COUNT = 20

"""
        TODO: Add case for missing config files
        TODO: Add dynamic scan range
        TODO: Resolve OSError
        TODO: Windows path conflicts
"""
def scan(ip, port=9090):
    s = socket.socket()
    conn = s.connect_ex((ip, port))
    s.close()
    if conn == 0:
        return ip
    else:
        return False


def get_ip_list(scan_range="192.168.1.1"):
    socket.setdefaulttimeout(1)
    template = '.'.join(scan_range.split(".")[:-1]) + '.'
    pool = ThreadPool(THREAD_COUNT)
    results = pool.map(scan, [template + str(i) for i in range(256)])
    pool.close()
    results = [res for res in results if res != False]
    socket.setdefaulttimeout(None)
    return results


def update_json(data: dict, file_name='client.json'):
    with open(file_name, 'r') as f:
        d = json.load(f)
    d.update(data)
    with open(file_name, 'w') as f:
        json.dump(d, f)


def menu():
    for i, choice in enumerate(['Server', 'Client']):
        print("%d) %s" % (i + 1, choice))
    choice = int(input(">> "))
    if choice == 1:
        d = {}
        local_path = input("Enter absolute path: ")
        d[local_path] = {}
        d[local_path]['user'] = sha1(bytes(local_path.encode())).hexdigest()
        d[local_path]['password'] = d[local_path]['user'][-15:]
        d[local_path]['user'] = d[local_path]['user'][:5]
        d[local_path]['read_only'] = input("Read only? [Y/N]:").lower() == 'y'
        s = socket.socket()
        input("Make sure client is running!! <Press Enter to continue>")
        print("Scanning ip, please wait...")
        ip = get_ip_list()
        for i, j in enumerate(ip):
            print("%d) %s" % (i + 1, j))
        x = input(
            "Enter a space delimited list of INDEX of ip you want to connect to: "
        ).split()
        x = [ip[int(i) - 1] for i in x]
        share = input("Do you want to share ip's with others as well[Y/N]: "
                      ).lower() == 'y'
        update_json(d,file_name='server.json')
        if share: d[local_path]['ip'] = x
        for i in x:
            s.connect((i, 9090))
            data = json.dumps(d)
            s.send(data.encode())
            s.close()

    if choice == 2:
        s = socket.socket()
        s.bind(('0.0.0.0', 9090))
        s.listen(1)
        print("Client is running ")
        msg = ''
        while len(msg) < 10:
            conn, addr = s.accept()
            msg = conn.recv(1024).decode()
        d = json.loads(msg)
        local_path=input("Enter local path: ")
        remote_path=list(d.keys())[0]
        d[local_path]= d.pop( remote_path )
        s.close()
        update_json(d)


if __name__ == "__main__":
    menu()
