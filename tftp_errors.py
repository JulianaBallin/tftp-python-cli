"""
TFTP Error Handling Module

This module provides centralized error handling utilities for TFTP client and server.
Includes error packet encoding/decoding, timeout management, file validation,
and user-friendly error messages.

Author: Renato Barbosa
Date: March 2026
"""

import logging
import socket
import struct
import sys
import os
from enum import IntEnum
from datetime import datetime
from typing import Tuple, Optional, Union, Dict, Any

class TFTPErrorCode(IntEnum):
    """TFTP error codes as defined by RFC 1350"""
    NOT_DEFINED = 0       # Not defined, see error message
    FILE_NOT_FOUND = 1    # File not found
    ACCESS_VIOLATION = 2  # Access violation
    DISK_FULL = 3         # Disk full or allocation exceeded
    ILLEGAL_OP = 4        # Illegal TFTP operation
    UNKNOWN_TID = 5       # Unknown transfer ID
    FILE_EXISTS = 6       # File already exists
    NO_USER = 7           # No such user

class ErrorMessages:
    """Standardized error messages for user display"""
    messages: Dict[TFTPErrorCode, str] = {
        TFTPErrorCode.NOT_DEFINED: "Unknown error occurred",
        TFTPErrorCode.FILE_NOT_FOUND: "File not found on server",
        TFTPErrorCode.ACCESS_VIOLATION: "Permission denied",
        TFTPErrorCode.DISK_FULL: "Disk full - cannot write",
        TFTPErrorCode.ILLEGAL_OP: "Invalid TFTP operation",
        TFTPErrorCode.UNKNOWN_TID: "Invalid transfer ID",
        TFTPErrorCode.FILE_EXISTS: "File already exists",
        TFTPErrorCode.NO_USER: "User not authenticated"
    }

def setup_error_logging(log_file: str = "tftp_errors.log", verbose: bool = True) -> logging.Logger:
    """
    Configure logging system for error tracking.

    Args:
        log_file: Path to log file
        verbose: If True, also output to console

    Returns:
        logging.Logger: Configured logger instance
    """
    handlers = [logging.FileHandler(log_file)]
    if verbose:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    return logging.getLogger('TFTP-Errors')


# Global logger instance
logger = setup_error_logging()

def encode_error(error_code: Union[int, TFTPErrorCode], error_message: str = "") -> bytes:
    """
    Encode a TFTP ERROR packet (opcode 5).

    Args:
        error_code: Error code (0-7)
        error_message: Optional descriptive message

    Returns:
        bytes: Encoded error packet ready for network transmission

    Example:
        >>> packet = encode_error(1, "File not found")
        >>> sock.sendto(packet, client_address)
    """
    if isinstance(error_code, TFTPErrorCode):
        error_code = error_code.value

    # Packet structure: opcode (2 bytes) + error_code (2 bytes) + error_msg + null byte
    opcode = 5  # ERROR packet
    error_msg_encoded = error_message.encode('utf-8') + b'\x00'

    return struct.pack(f'>HH{len(error_msg_encoded)}s', opcode, error_code, error_msg_encoded)

def decode_error(packet: bytes) -> Tuple[int, str]:
    """
    Decode a TFTP ERROR packet.

    Args:
        packet: Raw packet bytes received from network

    Returns:
        Tuple[int, str]: (error_code, error_message)

    Raises:
        ValueError: If packet is invalid or not an ERROR packet

    Example:
        >>> try:
        >>>     code, msg = decode_error(received_data)
        >>>     print(f"Error {code}: {msg}")
        >>> except ValueError as e:
        >>>     print(f"Invalid packet: {e}")
    """
    if len(packet) < 4:
        raise ValueError(f"Packet too short for ERROR: {len(packet)} bytes")

    opcode = struct.unpack('>H', packet[:2])[0]
    if opcode != 5:
        raise ValueError(f"Expected opcode 5 (ERROR), got {opcode}")

    error_code = struct.unpack('>H', packet[2:4])[0]

    # Extract message (up to null byte)
    msg_bytes = packet[4:]
    null_pos = msg_bytes.find(b'\x00')
    if null_pos == -1:
        error_msg = msg_bytes.decode('utf-8', errors='ignore')
    else:
        error_msg = msg_bytes[:null_pos].decode('utf-8', errors='ignore')

    return error_code, error_msg

def send_error_response(sock: socket.socket, client_addr: Tuple[str, int],
                        error_code: Union[int, TFTPErrorCode],
                        error_message: str = "") -> bool:
    """
    Send an error packet to client and log the event.

    Args:
        sock: UDP socket
        client_addr: Client address (ip, port)
        error_code: Error code
        error_message: Descriptive message

    Returns:
        bool: True if sent successfully, False otherwise

    Example (server):
        >>> if not os.path.exists(filename):
        >>>     send_error_response(sock, client_addr,
        >>>                         TFTPErrorCode.FILE_NOT_FOUND,
        >>>                         f"File {filename} not found")
    """
    try:
        error_packet = encode_error(error_code, error_message)
        sock.sendto(error_packet, client_addr)

        # Log the error
        if isinstance(error_code, TFTPErrorCode):
            code_name = error_code.name
            code_value = error_code.value
        else:
            code_name = "UNKNOWN"
            code_value = error_code

        logger.warning(
            f"Error {code_value} ({code_name}) sent to "
            f"{client_addr[0]}:{client_addr[1]} - {error_message}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send error packet: {e}")
        return False
