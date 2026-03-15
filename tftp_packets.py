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

import struct
from typing import Tuple, Union, Optional
from enum import IntEnum


class Opcode(IntEnum):
    """TFTP opcode values."""
    RRQ = 1  # Read request
    WRQ = 2  # Write request
    DATA = 3  # Data packet
    ACK = 4  # Acknowledgment
    ERROR = 5  # Error packet


class ErrorCode(IntEnum):
    """TFTP error code values."""
    NOT_DEFINED = 0
    FILE_NOT_FOUND = 1
    ACCESS_VIOLATION = 2
    DISK_FULL = 3
    ILLEGAL_OPERATION = 4
    UNKNOWN_TID = 5
    FILE_EXISTS = 6
    NO_SUCH_USER = 7

class TFTPErrorCode:
    NOT_DEFINED = 0
    FILE_NOT_FOUND = 1
    ACCESS_VIOLATION = 2
    DISK_FULL = 3
    ILLEGAL_OP = 4
    UNKNOWN_TID = 5
    FILE_EXISTS = 6
    NO_USER = 7

class TFTPPacket:
    """TFTP packet encoder/decoder."""
    
    # Default mode for transfers
    DEFAULT_MODE = 'octet'
    
    # Maximum data size per packet
    MAX_DATA_SIZE = 512
    
    @classmethod
    def encode_rrq(cls, filename: str, mode: str = DEFAULT_MODE) -> bytes:
        """
        Encode a Read Request packet.
        
        Args:
            filename: Name of file to read
            mode: Transfer mode (usually 'octet')
            
        Returns:
            Encoded packet as bytes
            
        Raises:
            ValueError: If filename is empty
        """
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        # Format: opcode (2 bytes) + filename + 0 + mode + 0
        return struct.pack(f'>H{len(filename)}sB{len(mode)}sB', 
                          Opcode.RRQ, 
                          filename.encode('ascii'), 
                          0, 
                          mode.encode('ascii'), 
                          0)
    
    @classmethod
    def encode_wrq(cls, filename: str, mode: str = DEFAULT_MODE) -> bytes:
        """
        Encode a Write Request packet.
        
        Args:
            filename: Name of file to write
            mode: Transfer mode (usually 'octet')
            
        Returns:
            Encoded packet as bytes
            
        Raises:
            ValueError: If filename is empty
        """
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        # Format: opcode (2 bytes) + filename + 0 + mode + 0
        return struct.pack(f'>H{len(filename)}sB{len(mode)}sB', 
                          Opcode.WRQ, 
                          filename.encode('ascii'), 
                          0, 
                          mode.encode('ascii'), 
                          0)
    
    @classmethod
    def encode_data(cls, block_number: int, data: bytes) -> bytes:
        """
        Encode a Data packet.
        
        Args:
            block_number: Block number (1-65535)
            data: Data to send (0-512 bytes)
            
        Returns:
            Encoded packet as bytes
            
        Raises:
            ValueError: If block number is invalid or data too large
        """
        if not (1 <= block_number <= 65535):
            raise ValueError(f"Invalid block number: {block_number}")
        
        if len(data) > cls.MAX_DATA_SIZE:
            raise ValueError(f"Data too large: {len(data)} bytes (max {cls.MAX_DATA_SIZE})")
        
        # Format: opcode (2 bytes) + block number (2 bytes) + data
        return struct.pack(f'>HH{len(data)}s', Opcode.DATA, block_number, data)
    
    @classmethod
    def encode_ack(cls, block_number: int) -> bytes:
        """
        Encode an Acknowledgment packet.
        
        Args:
            block_number: Block number being acknowledged
            
        Returns:
            Encoded packet as bytes
            
        Raises:
            ValueError: If block number is invalid
        """
        if not (0 <= block_number <= 65535):
            raise ValueError(f"Invalid block number: {block_number}")
        
        # Format: opcode (2 bytes) + block number (2 bytes)
        return struct.pack('>HH', Opcode.ACK, block_number)
    
    @classmethod
    def encode_error(cls, error_code: int, error_msg: str) -> bytes:
        """
        Encode an Error packet.
        
        Args:
            error_code: Error code from ErrorCode enum
            error_msg: Error message
            
        Returns:
            Encoded packet as bytes
            
        Raises:
            ValueError: If error code is invalid
        """
        if not (0 <= error_code <= 7):
            raise ValueError(f"Invalid error code: {error_code}")
        
        # Allow empty message (RFC 1350 allows empty message)
        if error_msg is None:
            error_msg = ""
        
        # Format: opcode (2 bytes) + error code (2 bytes) + error message + 0
        return struct.pack(f'>HH{len(error_msg)}sB', 
                          Opcode.ERROR, 
                          error_code, 
                          error_msg.encode('ascii'), 
                          0)
    
    @classmethod
    def decode(cls, data: bytes) -> Tuple[int, Union[str, int, Tuple[int, bytes], Tuple[int, str]]]:
        """
        Decode a TFTP packet.
        
        Args:
            data: Raw packet data
            
        Returns:
            Tuple of (opcode, decoded_data)
            - For RRQ/WRQ: (opcode, filename)
            - For DATA: (opcode, (block_number, data))
            - For ACK: (opcode, block_number)
            - For ERROR: (opcode, (error_code, error_msg))
            
        Raises:
            ValueError: If packet format is invalid or opcode unknown
        """
        if len(data) < 2:
            raise ValueError(f"Packet too short: {len(data)} bytes")
        
        # Extract opcode
        opcode = struct.unpack('>H', data[:2])[0]
        
        if opcode == Opcode.RRQ or opcode == Opcode.WRQ:
            # Decode RRQ/WRQ: filename + 0 + mode + 0
            try:
                # Split by null bytes
                parts = data[2:].split(b'\x00')
                if len(parts) < 2:
                    raise ValueError("Invalid RRQ/WRQ format")
                
                filename = parts[0].decode('ascii')
                # mode = parts[1].decode('ascii')  # mode is optional for return
                
                return opcode, filename
            except (UnicodeDecodeError, IndexError) as e:
                raise ValueError(f"Invalid RRQ/WRQ encoding: {e}")
        
        elif opcode == Opcode.DATA:
            # Decode DATA: block number (2 bytes) + data
            if len(data) < 4:
                raise ValueError("DATA packet too short")
            
            block_number = struct.unpack('>H', data[2:4])[0]
            packet_data = data[4:]
            
            if len(packet_data) > cls.MAX_DATA_SIZE:
                raise ValueError(f"DATA too large: {len(packet_data)} bytes")
            
            return opcode, (block_number, packet_data)
        
        elif opcode == Opcode.ACK:
            # Decode ACK: block number (2 bytes)
            if len(data) != 4:
                raise ValueError(f"Invalid ACK packet size: {len(data)} bytes")
            
            block_number = struct.unpack('>H', data[2:4])[0]
            return opcode, block_number
        
        elif opcode == Opcode.ERROR:
            # Decode ERROR: error code (2 bytes) + error message + 0
            if len(data) < 4:
                raise ValueError("ERROR packet too short")
            
            error_code = struct.unpack('>H', data[2:4])[0]
            
            # Extract error message (until null byte)
            error_msg = ""
            if len(data) > 4:
                null_pos = data.find(b'\x00', 4)
                if null_pos > 4:
                    error_msg = data[4:null_pos].decode('ascii')
            
            return opcode, (error_code, error_msg)
        
        else:
            raise ValueError(f"Unknown opcode: {opcode}")
