#!/usr/bin/env python3
"""
TFTP Server Implementation

This module implements a Trivial File Transfer Protocol (TFTP) server
as defined in RFC 1350. The server handles read requests (RRQ) and
write requests (WRQ) from clients, transferring files in 512-byte blocks.

Usage:
    python server.py --host 0.0.0.0 --port 6969 --directory storage

Author: Team TFTP
Date: March 2026
"""

import argparse
import logging
import socket
import os
import sys
from typing import Tuple, Optional

from tftp_packets import TFTPPacket, Opcode, ErrorCode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TFTPServer:
    """Main TFTP server class handling client requests."""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 69, directory: str = 'storage'):
        """
        Initialize TFTP server.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            directory: Base directory for file operations
        """
        self.host = host
        self.port = port
        self.directory = directory
        self.socket: Optional[socket.socket] = None
        self.timeout_seconds = 5.0
        self.max_retries = 5

    def _safe_path(self, filename: str) -> Optional[str]:
        """
        Return a safe absolute path for file operations or None if invalid.

        Prevents path traversal outside the configured storage directory.
        """
        base_dir = os.path.abspath(self.directory)
        target = os.path.abspath(os.path.join(base_dir, filename))

        if not target.startswith(base_dir + os.sep) and target != base_dir:
            return None

        return target

    @staticmethod
    def _send_error(sock: socket.socket, addr: Tuple[str, int], code: ErrorCode, message: str) -> None:
        """Send a TFTP ERROR packet to a remote address."""
        packet = TFTPPacket.encode_error(int(code), message)
        sock.sendto(packet, addr)

    def _handle_write_request(self, filename: str, client_addr: Tuple[str, int]) -> None:
        """Handle WRQ operation (client uploads a file to server)."""
        file_path = self._safe_path(filename)
        if not file_path:
            self._send_error(
                self.socket,
                client_addr,
                ErrorCode.ACCESS_VIOLATION,
                "Invalid filename or path traversal attempt"
            )
            return

        if os.path.isdir(file_path):
            self._send_error(self.socket, client_addr, ErrorCode.ACCESS_VIOLATION, "Target is a directory")
            return

        if os.path.exists(file_path):
            self._send_error(self.socket, client_addr, ErrorCode.FILE_EXISTS, "File already exists")
            return

        transfer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        transfer_socket.settimeout(self.timeout_seconds)

        success = False
        retries = 0
        expected_block = 1

        try:
            logger.info(f"Starting WRQ from {client_addr} -> {file_path}")

            with open(file_path, 'wb') as output_file:
                # WRQ handshake: server acknowledges block 0 to start transfer.
                transfer_socket.sendto(TFTPPacket.encode_ack(0), client_addr)

                while True:
                    try:
                        packet, addr = transfer_socket.recvfrom(4 + TFTPPacket.MAX_DATA_SIZE)
                    except socket.timeout:
                        retries += 1
                        if retries > self.max_retries:
                            logger.warning(f"Timeout receiving DATA from {client_addr} (max retries reached)")
                            self._send_error(
                                transfer_socket,
                                client_addr,
                                ErrorCode.NOT_DEFINED,
                                "Transfer timeout"
                            )
                            break

                        # Retransmit last ACK to recover from packet loss.
                        transfer_socket.sendto(TFTPPacket.encode_ack((expected_block - 1) % 65536), client_addr)
                        continue

                    retries = 0

                    if addr != client_addr:
                        # Per RFC, unknown transfer IDs receive ERROR code 5.
                        self._send_error(
                            transfer_socket,
                            addr,
                            ErrorCode.UNKNOWN_TID,
                            "Unknown transfer ID"
                        )
                        continue

                    try:
                        opcode, decoded = TFTPPacket.decode(packet)
                    except ValueError as exc:
                        logger.warning(f"Invalid packet from {client_addr}: {exc}")
                        self._send_error(
                            transfer_socket,
                            client_addr,
                            ErrorCode.ILLEGAL_OPERATION,
                            "Malformed packet"
                        )
                        break

                    if opcode == Opcode.DATA:
                        block_number, chunk = decoded

                        if block_number == expected_block:
                            output_file.write(chunk)
                            output_file.flush()
                            transfer_socket.sendto(TFTPPacket.encode_ack(block_number), client_addr)

                            if len(chunk) < TFTPPacket.MAX_DATA_SIZE:
                                success = True
                                logger.info(
                                    f"WRQ completed for {filename} from {client_addr}"
                                )
                                break

                            expected_block = (expected_block + 1) % 65536
                        elif block_number == ((expected_block - 1) % 65536):
                            # Duplicate DATA packet: re-send ACK and continue.
                            transfer_socket.sendto(TFTPPacket.encode_ack(block_number), client_addr)
                        else:
                            self._send_error(
                                transfer_socket,
                                client_addr,
                                ErrorCode.ILLEGAL_OPERATION,
                                f"Unexpected block number {block_number}, expected {expected_block}"
                            )
                            break
                    elif opcode == Opcode.ERROR:
                        error_code, message = decoded
                        logger.warning(
                            f"Client {client_addr} aborted transfer with error {error_code}: {message}"
                        )
                        break
                    else:
                        self._send_error(
                            transfer_socket,
                            client_addr,
                            ErrorCode.ILLEGAL_OPERATION,
                            "Expected DATA packet during WRQ transfer"
                        )
                        break
        except OSError as exc:
            logger.error(f"File write error for {file_path}: {exc}")
            self._send_error(self.socket, client_addr, ErrorCode.DISK_FULL, "Unable to write file")
        finally:
            transfer_socket.close()

            if not success and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as exc:
                    logger.warning(f"Could not remove incomplete file {file_path}: {exc}")
        
    def start(self) -> None:
        """Start the TFTP server and begin listening for requests."""
        logger.info(f"Starting TFTP server on {self.host}:{self.port}")
        logger.info(f"Storage directory: {self.directory}")

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))

        logger.info("Server ready to receive requests")

        while True:
            packet, client_addr = self.socket.recvfrom(516)

            try:
                opcode, decoded = TFTPPacket.decode(packet)
            except ValueError as exc:
                logger.warning(f"Malformed request from {client_addr}: {exc}")
                self._send_error(self.socket, client_addr, ErrorCode.ILLEGAL_OPERATION, "Malformed request")
                continue

            if opcode == Opcode.WRQ:
                filename = decoded
                self._handle_write_request(filename, client_addr)
            elif opcode == Opcode.RRQ:
                self._send_error(
                    self.socket,
                    client_addr,
                    ErrorCode.ILLEGAL_OPERATION,
                    "RRQ not implemented in this feature branch"
                )
            else:
                self._send_error(
                    self.socket,
                    client_addr,
                    ErrorCode.ILLEGAL_OPERATION,
                    "Only RRQ/WRQ requests are accepted on the main socket"
                )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='TFTP Server Implementation')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=6969, help='Port to listen on')
    parser.add_argument('--directory', default='storage', help='Storage directory')
    return parser.parse_args()


def main():
    """Main entry point for TFTP server."""
    args = parse_arguments()
    
    # Create storage directory if it doesn't exist
    os.makedirs(args.directory, exist_ok=True)
    
    server = TFTPServer(args.host, args.port, args.directory)
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
