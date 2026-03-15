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
import os
import sys

from tftp_packets import TFTPPacket, Opcode, ErrorCode

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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

