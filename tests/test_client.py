import unittest
import socket
import threading
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client import TFTPClient
from tftp_packets import TFTPPacket

class TestClientIntegration(unittest.TestCase):
    def setUp(self):
        self.host = "127.0.0.1"
        self.test_dir = tempfile.TemporaryDirectory()
        
        # Find a free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, 0))
        self.port = sock.getsockname()[1]
        sock.close()

    def tearDown(self):
        self.test_dir.cleanup()

    def _simulate_server_get(self, content_to_send):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(3.0)
        try:
            # 1. Wait for RRQ
            _, addr = sock.recvfrom(516)
            # 2. Send DATA block 1
            sock.sendto(TFTPPacket.encode_data(1, content_to_send), addr)
            # 3. Wait for ACK 1
            sock.recvfrom(516)
        except socket.timeout:
            pass
        finally:
            sock.close()

    def _simulate_server_put(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(3.0)
        self.received_data = b""
        try:
            # 1. Wait for WRQ
            _, addr = sock.recvfrom(516)
            # 2. Send ACK 0
            sock.sendto(TFTPPacket.encode_ack(0), addr)
            # 3. Wait for DATA block 1
            packet, _ = sock.recvfrom(516)
            _, (_, data) = TFTPPacket.decode(packet)
            self.received_data = data
            # 4. Send ACK 1
            sock.sendto(TFTPPacket.encode_ack(1), addr)
        except socket.timeout:
            pass
        finally:
            sock.close()

    def test_tftp_get_integration(self):
        content = b"Integration test GET data"
        local_file = os.path.join(self.test_dir.name, "download.txt")
        
        thread = threading.Thread(target=self._simulate_server_get, args=(content,))
        thread.start()

        client = TFTPClient(self.host, self.port)
        try:
            client.get("remote.txt", local_file)
        finally:
            client.socket.close()
        
        thread.join()

        self.assertTrue(os.path.exists(local_file))
        with open(local_file, "rb") as f:
            self.assertEqual(f.read(), content)

    def test_tftp_put_integration(self):
        content = b"Integration test PUT data"
        local_file = os.path.join(self.test_dir.name, "upload.txt")
        with open(local_file, "wb") as f:
            f.write(content)

        thread = threading.Thread(target=self._simulate_server_put)
        thread.start()

        client = TFTPClient(self.host, self.port)
        try:
            client.put(local_file, "remote.txt")
        finally:
            client.socket.close()
        
        thread.join()

        self.assertEqual(self.received_data, content)

if __name__ == '__main__':
    unittest.main()
