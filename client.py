#!/usr/bin/env python3
"""
TFTP Client Implementation

This module implements a Trivial File Transfer Protocol (TFTP) client
as defined in RFC 1350. The client can send read requests (RRQ) to
download files and write requests (WRQ) to upload files to a TFTP server.

Usage:
    python client.py get --host 127.0.0.1 --port 6969 --remote file.txt --local file.txt
    python client.py put --host 127.0.0.1 --port 6969 --local file.txt --remote file.txt

Author: Team TFTP
Date: March 2026
"""

import argparse
import logging
import socket
import sys
import os
from typing import Tuple, Optional

from tftp_packets import TFTPPacket, Opcode, ErrorCode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TFTPClient:
    """TFTP client for file upload and download."""
    
    def __init__(self, host: str, port: int = 69):
        """
        Initialize TFTP client.
        
        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host
        self.port = port
        self.timeout_seconds = 5.0
        self.max_retries = 5

    def _send_error(self, sock: socket.socket, addr: Tuple[str, int], code: ErrorCode, message: str) -> None:
        """Send a TFTP ERROR packet."""
        packet = TFTPPacket.encode_error(int(code), message)
        sock.sendto(packet, addr)

    def get(self, remote_file: str, local_file: str) -> bool:
        """
        Download a file from the server (RRQ).
        
        Args:
            remote_file: Name of the file on the server
            local_file: Name of the file to save locally
            
        Returns:
            True if successful, False otherwise
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout_seconds)
        
        server_addr = (self.host, self.port)
        transfer_addr = None
        
        success = False
        retries = 0
        expected_block = 1
        
        try:
            logger.info(f"Requesting '{remote_file}' from {self.host}:{self.port}")
            
            # Send RRQ
            rrq_packet = TFTPPacket.encode_rrq(remote_file)
            sock.sendto(rrq_packet, server_addr)
            
            with open(local_file, 'wb') as f:
                while True:
                    try:
                        packet, addr = sock.recvfrom(4 + TFTPPacket.MAX_DATA_SIZE)
                        
                        # Set transfer address on first packet
                        if transfer_addr is None:
                            transfer_addr = addr
                        
                        if addr != transfer_addr:
                            self._send_error(sock, addr, ErrorCode.UNKNOWN_TID, "Unknown transfer ID")
                            continue
                            
                        opcode, decoded = TFTPPacket.decode(packet)
                        
                        if opcode == Opcode.DATA:
                            block_number, data = decoded
                            
                            if block_number == expected_block:
                                f.write(data)
                                f.flush()
                                # Send ACK
                                sock.sendto(TFTPPacket.encode_ack(block_number), transfer_addr)
                                
                                if len(data) < TFTPPacket.MAX_DATA_SIZE:
                                    success = True
                                    logger.info(f"Download of '{remote_file}' complete.")
                                    break
                                    
                                expected_block = (expected_block + 1) % 65536
                                retries = 0
                            elif block_number == (expected_block - 1) % 65536:
                                # Duplicate DATA, re-send ACK
                                sock.sendto(TFTPPacket.encode_ack(block_number), transfer_addr)
                            else:
                                logger.error(f"Unexpected block number {block_number}, expected {expected_block}")
                                break
                                
                        elif opcode == Opcode.ERROR:
                            error_code, message = decoded
                            logger.error(f"Server error {error_code}: {message}")
                            break
                        else:
                            logger.error("Unexpected opcode received")
                            break
                            
                    except socket.timeout:
                        retries += 1
                        if retries > self.max_retries:
                            logger.error("Timeout reached. Aborting.")
                            break
                        
                        logger.warning(f"Timeout, retrying... ({retries}/{self.max_retries})")
                        if expected_block == 1:
                            # Re-send RRQ
                            sock.sendto(rrq_packet, server_addr)
                        else:
                            # Re-send last ACK
                            sock.sendto(TFTPPacket.encode_ack((expected_block - 1) % 65536), transfer_addr)
                            
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            sock.close()
            if not success and os.path.exists(local_file):
                os.remove(local_file)
                
        return success

    def put(self, local_file: str, remote_file: str) -> bool:
        """
        Upload a file to the server (WRQ).
        
        Args:
            local_file: Name of the local file to upload
            remote_file: Name to save the file as on the server
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(local_file):
            logger.error(f"Local file '{local_file}' does not exist.")
            return False
            
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout_seconds)
        
        server_addr = (self.host, self.port)
        transfer_addr = None
        
        success = False
        retries = 0
        block_number = 1
        
        try:
            logger.info(f"Uploading '{local_file}' to {self.host}:{self.port} as '{remote_file}'")
            
            # Send WRQ
            wrq_packet = TFTPPacket.encode_wrq(remote_file)
            sock.sendto(wrq_packet, server_addr)
            
            # Wait for ACK 0
            try:
                packet, addr = sock.recvfrom(516)
                transfer_addr = addr
                opcode, decoded = TFTPPacket.decode(packet)
                
                if opcode == Opcode.ACK and decoded == 0:
                    pass # Handshake complete
                elif opcode == Opcode.ERROR:
                    error_code, message = decoded
                    logger.error(f"Server error {error_code}: {message}")
                    return False
                else:
                    logger.error("Unexpected response to WRQ")
                    return False
            except socket.timeout:
                logger.error("Timeout waiting for WRQ acknowledgment.")
                return False
                
            with open(local_file, 'rb') as f:
                while True:
                    data = f.read(TFTPPacket.MAX_DATA_SIZE)
                    data_packet = TFTPPacket.encode_data(block_number, data)
                    
                    # Send DATA and wait for ACK
                    ack_received = False
                    while not ack_received:
                        sock.sendto(data_packet, transfer_addr)
                        
                        try:
                            packet, addr = sock.recvfrom(516)
                            if addr != transfer_addr:
                                self._send_error(sock, addr, ErrorCode.UNKNOWN_TID, "Unknown transfer ID")
                                continue
                                
                            opcode, decoded = TFTPPacket.decode(packet)
                            if opcode == Opcode.ACK:
                                if decoded == block_number:
                                    ack_received = True
                                    block_number = (block_number + 1) % 65536
                                    retries = 0
                                elif decoded == (block_number - 1) % 65536:
                                    # Duplicate ACK, ignore and re-send current block
                                    continue
                            elif opcode == Opcode.ERROR:
                                error_code, message = decoded
                                logger.error(f"Server error {error_code}: {message}")
                                return False
                        except socket.timeout:
                            retries += 1
                            if retries > self.max_retries:
                                logger.error("Timeout waiting for ACK. Aborting.")
                                return False
                            logger.warning(f"Timeout waiting for ACK {block_number}, retrying... ({retries}/{self.max_retries})")

                    if len(data) < TFTPPacket.MAX_DATA_SIZE:
                        success = True
                        logger.info(f"Upload of '{local_file}' complete.")
                        break
                        
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            sock.close()
            
        return success


def main():
    parser = argparse.ArgumentParser(description="TFTP Client")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Get command
    get_parser = subparsers.add_parser("get", help="Download a file")
    get_parser.add_argument("--host", required=True, help="Server host")
    get_parser.add_argument("--port", type=int, default=6969, help="Server port")
    get_parser.add_argument("--remote", required=True, help="Remote filename")
    get_parser.add_argument("--local", required=True, help="Local filename")
    
    # Put command
    put_parser = subparsers.add_parser("put", help="Upload a file")
    put_parser.add_argument("--host", required=True, help="Server host")
    put_parser.add_argument("--port", type=int, default=6969, help="Server port")
    put_parser.add_argument("--local", required=True, help="Local filename")
    put_parser.add_argument("--remote", required=True, help="Remote filename")
    
    args = parser.parse_args()
    
    if args.command == "get":
        client = TFTPClient(args.host, args.port)
        if client.get(args.remote, args.local):
            sys.exit(0)
        else:
            sys.exit(1)
    elif args.command == "put":
        client = TFTPClient(args.host, args.port)
        if client.put(args.local, args.remote):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
