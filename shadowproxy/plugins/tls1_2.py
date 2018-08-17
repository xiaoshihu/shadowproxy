import random
from .. import gvars
from ..protocols.tls1_2 import TLS1_2Reader, Receiver


def pack_uint16(s):
    return len(s).to_bytes(2, "big") + s


class TLS1_2Plugin:
    name = "tls1.2"

    def __init__(self):
        self.tls_version = b"\x03\x03"
        self.hosts = (b"cloudfront.net", b"cloudfront.com")
        self.time_tolerance = 5 * 60

    async def init_server(self, client):
        tls_reader = TLS1_2Reader(self)
        hello_sent = False
        while True:
            data = await client.recv(gvars.PACKET_SIZE)
            if not data:
                return
            tls_reader.send(data)
            if not hello_sent:
                server_hello = tls_reader.read()
                if not server_hello:
                    continue
                await client.sendall(server_hello)
                hello_sent = True
            else:
                if not tls_reader.has_result:
                    continue
                break
        redundant = tls_reader.input.read()
        # if redundant:
        recv = client.recv

        async def disposable_recv(size):
            client.redundant = redundant
            client.recv = recv
            return redundant

        client.recv = disposable_recv

    def make_recv_func(self, client):
        receiver = Receiver(self)

        async def recv(size):
            while True:
                data = await client.recv(size)
                if not data:
                    return data
                receiver.send(data)
                data = receiver.read()
                if data:
                    return data

        return recv

    def encode(self, data):
        ret = b""
        data = memoryview(data)
        while len(data) > 2048:
            size = min(random.randrange(4096) + 100, len(data))
            ret += b"\x17" + self.tls_version + size.to_bytes(2, "big") + data[:size]
            data = data[size:]
        if len(data) > 0:
            ret += b"\x17" + self.tls_version + pack_uint16(data)
        return ret