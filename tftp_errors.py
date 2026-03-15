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

