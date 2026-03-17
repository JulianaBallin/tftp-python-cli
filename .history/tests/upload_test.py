import socket
from tftp_packets import TFTPPacket, Opcode

SERVER = ("127.0.0.1", 6969)
FILENAME = "upload_teste.txt"
DATA = b"Ola do teste WRQ\n"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5)

sock.sendto(TFTPPacket.encode_wrq(FILENAME), SERVER)

packet, transfer_addr = sock.recvfrom(516)
opcode, block = TFTPPacket.decode(packet)
if opcode != Opcode.ACK or block != 0:
    raise RuntimeError(f"Esperava ACK 0, veio opcode={opcode}, block={block}")

sock.sendto(TFTPPacket.encode_data(1, DATA), transfer_addr)

packet, _ = sock.recvfrom(516)
opcode, block = TFTPPacket.decode(packet)
if opcode != Opcode.ACK or block != 1:
    raise RuntimeError(f"Esperava ACK 1, veio opcode={opcode}, block={block}")

print("Upload concluido com sucesso.")
sock.close()