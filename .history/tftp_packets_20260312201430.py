#!/usr/bin/env python3
"""
TFTP Packet Encoding and Decoding

This module handles the encoding and decoding of TFTP protocol packets
as defined in RFC 1350. It supports RRQ, WRQ, DATA, ACK, and ERROR packets.

Packet formats:
    - RRQ/WRQ: 2 bytes opcode + filename + 0 + mode + 0
    - DATA: 2 bytes opcode + 2 bytes block number + data (0-512 bytes)
    - ACK: 2 bytes opcode + 2 bytes block number
    - ERROR: 2 bytes opcode + 2 bytes error code + error message + 0

Author: Team TFTP
Date: March 2026
"""
