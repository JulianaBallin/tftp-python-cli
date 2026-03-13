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
