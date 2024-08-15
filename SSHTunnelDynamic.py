import asyncio
import asyncssh
import sys
import time
import threading
import socket
import errno

class OpenSSH:
    def __init__(self, host, username, password, port, known_hosts=None):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.known_hosts = known_hosts
        self.ssh_status = None

    async def run_client(self, stop):
        try:
            async with asyncssh.connect(
                host=self.host,
                username=self.username,
                password=self.password,
                known_hosts=self.known_hosts
            ) as conn:
                listener = await conn.forward_socks('127.0.0.1', self.port)
                self.ssh_status = True
                
                while not stop():
                    await asyncio.sleep(0.1)
        except (OSError, asyncssh.Error) as exc:
            self.ssh_status = False
            print('SSH connection failed: ' + str(exc))

    def thr(self, stop):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.run_client(stop))
        finally:
            loop.close()

    def waitResult(self):
        while self.ssh_status is None:
            time.sleep(0.1)
        return self.ssh_status

class SSHProxyController:
    def __init__(self, host, username, password, port, known_hosts=None, port_retry=100):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.known_hosts = known_hosts
        self.port_retry = port_retry
        self.stop_thread = False

    def start(self):
        while self.port_retry > 0:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(("127.0.0.1", self.port))
                s.close()
                break
            except socket.error as e:
                if e.errno == errno.EADDRINUSE:
                    self.port += 1
                    self.port_retry -= 1
                else:
                    return False, self.host, self.port
        else:
            return False, self.host, self.port

        myssh = OpenSSH(self.host, self.username, self.password, self.port)
        t1 = threading.Thread(target=myssh.thr, args=(lambda: self.stop_thread,))
        t1.daemon = True
        t1.start()
        return myssh.waitResult(), self.host, self.port

    def stop(self):
        self.stop_thread = True
