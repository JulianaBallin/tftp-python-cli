import unittest
import socket
import threading
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client import tftp_get, tftp_put
from tftp_packets import TFTPPacket

class TestClientIntegration(unittest.TestCase):
    def setUp(self):
        self.host = "127.0.0.1"
        self.test_dir = tempfile.TemporaryDirectory()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, 0))
        self.port = sock.getsockname()[1]
        sock.close()

    def tearDown(self):
        self.test_dir.cleanup()

    def _simulate_server_get(self, dados_para_enviar):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(3.0)
        try:
            _, addr = sock.recvfrom(516)
            sock.sendto(TFTPPacket.encode_data(1, dados_para_enviar), addr)
            sock.recvfrom(516)
        except socket.timeout:
            pass
        finally:
            sock.close()

    def _simulate_server_put(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(3.0)
        self.dados_recebidos = b""
        try:
            _, addr = sock.recvfrom(516)
            sock.sendto(TFTPPacket.encode_ack(0), addr)
            pacote_dados, _ = sock.recvfrom(516)
            _, (_, dados) = TFTPPacket.decode(pacote_dados)
            self.dados_recebidos = dados
            sock.sendto(TFTPPacket.encode_ack(1), addr)
        except socket.timeout:
            pass
        finally:
            sock.close()

    def test_tftp_get_network(self):
        content = b"Dados do teste de integracao GET"
        arquivo_local = os.path.join(self.test_dir.name, "download.txt")
        thread_server = threading.Thread(target=self._simulate_server_get, args=(content,))
        thread_server.start()

        tftp_get(self.host, self.port, "arquivo_remoto.txt", arquivo_local)
        thread_server.join()

        self.assertTrue(os.path.exists(arquivo_local), "O arquivo não foi criado pelo cliente.")
        with open(arquivo_local, "rb") as f:
            self.assertEqual(f.read(), content)

    def test_tftp_put_network(self):
        content_sent = b"Dados do teste de integracao PUT"
        arquivo_local = os.path.join(self.test_dir.name, "upload.txt")

        with open(arquivo_local, "wb") as f:
            f.write(content_sent)

        thread_server = threading.Thread(target=self._simulate_server_put)
        thread_server.start()

        tftp_put(self.host, self.port, arquivo_local, "remoto.txt")
        thread_server.join()

        self.assertEqual(self.dados_recebidos, content_sent, "O servidor não recebeu os bytes corretos.")

if __name__ == '__main__':
    unittest.main()