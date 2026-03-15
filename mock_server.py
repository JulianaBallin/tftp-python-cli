import socket
import sys
import os
from tftp_packets import TFTPPacket, Opcode

def start_mock_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('127.0.0.1', 6969))
    print("Mock TFTP Server listening on 127.0.0.1:6969...")
    
    try:
        # Wait for WRQ
        data, client_address = server_socket.recvfrom(4096)
        print(f"Received {len(data)} bytes from {client_address}")
        
        opcode, decoded = TFTPPacket.decode(data)
        if opcode == Opcode.WRQ:
            filename = decoded
            print(f"Success! Received WRQ for file '{filename}'")
            
            # Send ACK 0
            ack_packet = TFTPPacket.encode_ack(0)
            server_socket.sendto(ack_packet, client_address)
            print("Sent ACK 0")
            
            # Wait for DATA 1
            data, client_address = server_socket.recvfrom(4096)
            opcode, decoded = TFTPPacket.decode(data)
            
            if opcode == Opcode.DATA:
                block_num, file_data = decoded
                print(f"Success! Received DATA block {block_num} with {len(file_data)} bytes")
                
                # Save to storage
                filepath = os.path.join("storage", filename)
                with open(filepath, "wb") as f:
                    f.write(file_data)
                print(f"File successfully saved to {filepath}")
                
                # Send ACK 1
                ack_packet = TFTPPacket.encode_ack(1)
                server_socket.sendto(ack_packet, client_address)
                print("Sent ACK 1. Test complete!")
            else:
                print(f"Failed! Expected DATA but got opcode {opcode}")
        else:
            print(f"Failed! Expected WRQ but got opcode {opcode}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        server_socket.close()

if __name__ == '__main__':
    start_mock_server()
