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

class TimeoutHandler:
    """
    Manages timeouts and retransmissions for TFTP client.

    Implements exponential backoff for retry attempts.

    Example:
        >>> timeout_handler = TimeoutHandler(max_retries=3, timeout=2)
        >>> for attempt in range(timeout_handler.max_retries):
        >>>     try:
        >>>         sock.sendto(packet, server_addr)
        >>>         response, addr = sock.recvfrom(1024)
        >>>         timeout_handler.reset()  # Success
        >>>         break
        >>>     except socket.timeout:
        >>>         if not timeout_handler.should_retry():
        >>>             raise Exception("Server not responding")
        >>>         print(f"Timeout, retry {attempt+1}/{timeout_handler.max_retries}")
    """

    def __init__(self, max_retries: int = 3, timeout: float = 2.0,
                 backoff_factor: float = 1.5):
        """
        Initialize timeout handler.

        Args:
            max_retries: Maximum number of retry attempts
            timeout: Initial timeout in seconds
            backoff_factor: Multiplier for timeout on each retry
        """
        self.max_retries = max_retries
        self.initial_timeout = timeout
        self.backoff_factor = backoff_factor
        self.attempt = 0
        self.last_attempt_time: Optional[datetime] = None

    def should_retry(self) -> bool:
        """Check if another retry attempt is allowed."""
        self.attempt += 1
        self.last_attempt_time = datetime.now()
        return self.attempt < self.max_retries

    def get_current_timeout(self) -> float:
        """Get timeout for current attempt (with backoff applied)."""
        return self.initial_timeout * (self.backoff_factor ** self.attempt)

    def reset(self) -> None:
        """Reset attempt counter after successful operation."""
        self.attempt = 0
        self.last_attempt_time = None

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics of the timeout handler."""
        return {
            "attempts": self.attempt,
            "max_retries": self.max_retries,
            "current_timeout": self.get_current_timeout(),
            "last_attempt": self.last_attempt_time.isoformat() if self.last_attempt_time else None
        }

def validate_file_for_read(filepath: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate if a file can be read (for server RRQ handling).

    Args:
        filepath: Full path to file

    Returns:
        Tuple[bool, error_msg, error_code]:
            - (True, None, None) if valid
            - (False, error_message, error_code) if invalid

    Example (server):
        >>> ok, msg, code = validate_file_for_read("storage/file.txt")
        >>> if not ok:
        >>>     send_error_response(sock, client_addr, code, msg)
        >>>     return
    """
    if not os.path.exists(filepath):
        return False, f"File not found: {os.path.basename(filepath)}", TFTPErrorCode.FILE_NOT_FOUND

    if not os.path.isfile(filepath):
        return False, f"Not a regular file: {filepath}", TFTPErrorCode.ACCESS_VIOLATION

    if not os.access(filepath, os.R_OK):
        return False, f"Read permission denied: {filepath}", TFTPErrorCode.ACCESS_VIOLATION

    return True, None, None


def validate_file_for_write(filepath: str, overwrite: bool = False) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate if a file can be written (for server WRQ handling).

    Args:
        filepath: Full path to file
        overwrite: If True, allow overwriting existing file

    Returns:
        Tuple[bool, error_msg, error_code]
    """
    # Check directory existence and permissions
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        return False, f"Directory does not exist: {directory}", TFTPErrorCode.ACCESS_VIOLATION

    if directory and not os.access(directory, os.W_OK):
        return False, f"Write permission denied in directory: {directory}", TFTPErrorCode.ACCESS_VIOLATION

    # Check if file already exists
    if os.path.exists(filepath) and not overwrite:
        return False, f"File already exists: {filepath}", TFTPErrorCode.FILE_EXISTS

    # Basic disk space check (Unix-like systems only)
    try:
        if directory:
            stat = os.statvfs(directory)
            free_space = stat.f_frsize * stat.f_bavail
            if free_space < 1024:  # Minimum 1KB free
                return False, "Insufficient disk space", TFTPErrorCode.DISK_FULL
    except (AttributeError, OSError):
        # statvfs not available on Windows or error occurred
        pass

    return True, None, None

class TFTPError(Exception):
    """Base exception for TFTP-specific errors."""

    def __init__(self, message: str, error_code: int = 0):
        self.error_code = error_code
        self.message = message
        super().__init__(message)

    def to_packet(self) -> bytes:
        """Convert exception to TFTP error packet."""
        return encode_error(self.error_code, self.message)


def handle_socket_error(e: Exception, context: str = "") -> Tuple[str, int]:
    """
    Handle common socket errors and return user-friendly messages.

    Args:
        e: Caught exception
        context: Context where error occurred (e.g., "download", "upload")

    Returns:
        Tuple[str, int]: (user_friendly_message, error_code)

    Example:
        >>> try:
        >>>     sock.recvfrom(1024)
        >>> except Exception as e:
        >>>     msg, code = handle_socket_error(e, "receiving data")
        >>>     print(f"Error: {msg}")
    """
    error_context = f" during {context}" if context else ""

    if isinstance(e, socket.timeout):
        return f"Timeout{error_context}: server not responding", 1
    elif isinstance(e, ConnectionRefusedError):
        return f"Connection refused{error_context}: server unavailable", 2
    elif isinstance(e, socket.gaierror):
        return f"DNS error{error_context}: invalid address", 3
    elif isinstance(e, PermissionError):
        return f"Permission denied{error_context}", 4
    else:
        return f"Network error{error_context}: {str(e)}", 99

def print_user_error(error_code: Union[int, TFTPErrorCode], custom_message: str = "") -> None:
    """
    Display formatted error message for end user.

    Args:
        error_code: Error code
        custom_message: Additional context message

    Example:
        >>> print_user_error(1, "config.txt")
        Output: "ERROR: File not found - config.txt"
    """
    if isinstance(error_code, TFTPErrorCode):
        code = error_code.value
        base_msg = ErrorMessages.messages.get(error_code, "Unknown error")
    else:
        code = error_code
        try:
            base_msg = ErrorMessages.messages[TFTPErrorCode(code)]
        except KeyError:
            base_msg = f"Error {code}"

    if custom_message:
        full_message = f"{base_msg} - {custom_message}"
    else:
        full_message = base_msg

    print(f"ERROR: {full_message}")

    # Tips for specific error codes
    tips = {
        TFTPErrorCode.FILE_NOT_FOUND: "Tip: Check if file exists on server",
        TFTPErrorCode.ACCESS_VIOLATION: "Tip: Check file/directory permissions",
        TFTPErrorCode.DISK_FULL: "Tip: Free up disk space",
        TFTPErrorCode.UNKNOWN_TID: "Tip: Connection issue - try again",
    }

    tip = tips.get(TFTPErrorCode(code))
    if tip:
        print(f"{tip}")
