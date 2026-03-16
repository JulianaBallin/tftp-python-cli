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
import socket
import os
import sys

from tftp_packets import TFTPPacket, Opcode
from tftp_errors import TFTPErrorCode, ErrorMessages, setup_error_logging

# Configure logging
logger = setup_error_logging()


class TFTPClient:
    """Main TFTP client class handling file transfers."""

    TIMEOUT = 2.0
    MAX_RETRIES = 3

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server_address = (host, port)

        # Initialize UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.TIMEOUT)

    def _send_wrq_and_wait_ack(self, remote_filename: str) -> tuple:
        """Sends WRQ and waits for ACK 0 to establish the transfer ID (server TID)."""
        wrq_packet = TFTPPacket.encode_wrq(remote_filename)
        self.socket.sendto(wrq_packet, self.server_address)

        server_tid = None
        retries = 0
        while retries <= self.MAX_RETRIES:
            try:
                data, address = self.socket.recvfrom(4096)

                if server_tid is None:
                    server_tid = address
                elif address != server_tid:
                    logger.warning(f"Received packet from unknown address: {address}")
                    error_packet = TFTPPacket.encode_error(
                        TFTPErrorCode.UNKNOWN_TID,
                        ErrorMessages.messages[TFTPErrorCode.UNKNOWN_TID],
                    )
                    self.socket.sendto(error_packet, address)
                    continue

                opcode, decoded_data = TFTPPacket.decode(data)

                if opcode == Opcode.ERROR:
                    error_code, error_msg = decoded_data
                    logger.error(f"Server returned error {error_code}: {error_msg}")
                    sys.exit(1)

                if opcode == Opcode.ACK and decoded_data == 0:
                    logger.debug("Received ACK 0, server ready for data")
                    return server_tid
                else:
                    logger.warning(f"Expected ACK 0, got opcode {opcode}")

            except socket.timeout:
                retries += 1
                if retries > self.MAX_RETRIES:
                    logger.error("Timeout waiting for server to acknowledge WRQ")
                    sys.exit(1)
                logger.info("Timeout, retransmitting WRQ")
                self.socket.sendto(wrq_packet, self.server_address)

        logger.error("Transfer failed: could not establish connection with server")
        sys.exit(1)

    def _send_data_block_and_wait_ack(
        self, expected_block: int, data_packet: bytes, server_tid: tuple
    ) -> bool:
        """Sends a single DATA block and waits for the corresponding ACK."""
        retries = 0
        while retries <= self.MAX_RETRIES:
            self.socket.sendto(data_packet, server_tid)
            logger.debug(f"Sent DATA block {expected_block}")

            try:
                data, address = self.socket.recvfrom(4096)

                if address != server_tid:
                    logger.warning(
                        f"Received packet from {address}, expected {server_tid}"
                    )
                    error_packet = TFTPPacket.encode_error(
                        TFTPErrorCode.UNKNOWN_TID,
                        ErrorMessages.messages[TFTPErrorCode.UNKNOWN_TID],
                    )
                    self.socket.sendto(error_packet, address)
                    continue

                opcode, decoded_data = TFTPPacket.decode(data)

                if opcode == Opcode.ERROR:
                    error_code, error_msg = decoded_data
                    logger.error(f"Server returned error {error_code}: {error_msg}")
                    sys.exit(1)

                if opcode == Opcode.ACK:
                    ack_block = decoded_data
                    if ack_block == expected_block:
                        logger.debug(f"Received ACK for block {expected_block}")
                        return True
                    else:
                        logger.warning(
                            f"Received ACK for block {ack_block}, "
                            f"expected {expected_block}"
                        )

            except socket.timeout:
                retries += 1
                if retries > self.MAX_RETRIES:
                    logger.error(f"Timeout waiting for ACK {expected_block}")
                    sys.exit(1)
                logger.info(f"Timeout, retransmitting DATA block {expected_block}")

        return False

    def put(self, local_filename: str, remote_filename: str) -> None:
        """
        Upload a file to the server (WRQ).
        """
        if not os.path.exists(local_filename):
            logger.error(f"Local file '{local_filename}' does not exist.")
            sys.exit(1)

        logger.info(
            f"Starting upload of {local_filename} to {self.host}:{self.port} as {remote_filename}"
        )

        # 1. Send WRQ and get server Transaction ID
        server_tid = self._send_wrq_and_wait_ack(remote_filename)

        # 2. Setup DATA transfer
        expected_block = 1

        try:
            with open(local_filename, "rb") as f:
                while True:
                    file_data = f.read(512)
                    data_len = len(file_data)
                    data_packet = TFTPPacket.encode_data(expected_block, file_data)

                    # Send the data block and wait for ACK
                    ack_received = self._send_data_block_and_wait_ack(
                        expected_block, data_packet, server_tid
                    )

                    if not ack_received:
                        logger.error("Transfer failed after maximum retries")
                        sys.exit(1)

                    # Transfer complete if we read less than 512 bytes
                    if data_len < 512:
                        logger.info(
                            f"Upload of {local_filename} completed successfully"
                        )
                        break

                    # Increment block number (wrap around at 65535)
                    expected_block = (expected_block % 65535) + 1

        except IOError as e:
            logger.error(f"Error reading file '{local_filename}': {e}")
            sys.exit(1)

    def get(self, remote_filename: str, local_filename: str) -> None:
        """
        Download a file from the server (RRQ).
        To be implemented by another team member.
        """
        logger.error("GET operation not implemented yet.")
        sys.exit(1)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="TFTP Client Implementation")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Command to execute"
    )

    # GET command
    get_parser = subparsers.add_parser("get", help="Download a file from the server")
    get_parser.add_argument("--host", required=True, help="Server host IP")
    get_parser.add_argument("--port", type=int, default=69, help="Server port")
    get_parser.add_argument("--remote", required=True, help="Remote file name")
    get_parser.add_argument("--local", required=True, help="Local file name")

    # PUT command
    put_parser = subparsers.add_parser("put", help="Upload a file to the server")
    put_parser.add_argument("--host", required=True, help="Server host IP")
    put_parser.add_argument("--port", type=int, default=69, help="Server port")
    put_parser.add_argument("--local", required=True, help="Local file name")
    put_parser.add_argument("--remote", required=True, help="Remote file name")

    return parser.parse_args()


def main():
    """Main entry point for TFTP client."""
    args = parse_arguments()

    client = TFTPClient(args.host, args.port)

    try:
        if args.command == "get":
            client.get(args.remote, args.local)
        elif args.command == "put":
            client.put(args.local, args.remote)

    except KeyboardInterrupt:
        logger.info("Transfer interrupted by user")
        sys.exit(0)
    except ConnectionResetError:
        logger.error(
            "Target server not found or unavailable. "
            "Make sure the TFTP server is running on the correct port."
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Client error: {e}")
        sys.exit(1)
    finally:
        if hasattr(client, "socket") and client.socket:
            client.socket.close()


if __name__ == "__main__":
    main()
