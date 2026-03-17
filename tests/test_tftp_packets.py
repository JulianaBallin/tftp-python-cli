"""
Unit tests for TFTP packet encoding/decoding.
"""

import unittest
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tftp_packets import TFTPPacket, Opcode, ErrorCode


class TestOpcodeEnum(unittest.TestCase):
    """Test Opcode enum values."""
    
    def test_opcode_values(self):
        """Test that opcode values match RFC 1350."""
        self.assertEqual(Opcode.RRQ, 1)
        self.assertEqual(Opcode.WRQ, 2)
        self.assertEqual(Opcode.DATA, 3)
        self.assertEqual(Opcode.ACK, 4)
        self.assertEqual(Opcode.ERROR, 5)


class TestErrorCodeEnum(unittest.TestCase):
    """Test ErrorCode enum values."""
    
    def test_error_code_values(self):
        """Test that error code values match RFC 1350."""
        self.assertEqual(ErrorCode.NOT_DEFINED, 0)
        self.assertEqual(ErrorCode.FILE_NOT_FOUND, 1)
        self.assertEqual(ErrorCode.ACCESS_VIOLATION, 2)
        self.assertEqual(ErrorCode.DISK_FULL, 3)
        self.assertEqual(ErrorCode.ILLEGAL_OPERATION, 4)
        self.assertEqual(ErrorCode.UNKNOWN_TID, 5)
        self.assertEqual(ErrorCode.FILE_EXISTS, 6)
        self.assertEqual(ErrorCode.NO_SUCH_USER, 7)


class TestRRQEncodingDecoding(unittest.TestCase):
    """Test RRQ packet encoding and decoding."""
    
    def test_encode_rrq_basic(self):
        """Test basic RRQ encoding."""
        packet = TFTPPacket.encode_rrq("test.txt")
        
        # Expected format: opcode(1) + "test.txt" + 0 + "octet" + 0
        self.assertEqual(packet[0:2], b'\x00\x01')  # Opcode 1 (RRQ)
        
        # Decode and verify
        opcode, filename = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.RRQ)
        self.assertEqual(filename, "test.txt")
    
    def test_encode_rrq_with_mode(self):
        """Test RRQ encoding with custom mode."""
        packet = TFTPPacket.encode_rrq("file.bin", "octet")
        
        opcode, filename = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.RRQ)
        self.assertEqual(filename, "file.bin")
    
    def test_encode_rrq_empty_filename(self):
        """Test RRQ encoding with empty filename raises error."""
        with self.assertRaises(ValueError):
            TFTPPacket.encode_rrq("")


class TestWRQEncodingDecoding(unittest.TestCase):
    """Test WRQ packet encoding and decoding."""
    
    def test_encode_wrq_basic(self):
        """Test basic WRQ encoding."""
        packet = TFTPPacket.encode_wrq("upload.txt")
        
        self.assertEqual(packet[0:2], b'\x00\x02')  # Opcode 2 (WRQ)
        
        opcode, filename = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.WRQ)
        self.assertEqual(filename, "upload.txt")
    
    def test_encode_wrq_empty_filename(self):
        """Test WRQ encoding with empty filename raises error."""
        with self.assertRaises(ValueError):
            TFTPPacket.encode_wrq("")


class TestDATAEncodingDecoding(unittest.TestCase):
    """Test DATA packet encoding and decoding."""
    
    def test_encode_data_basic(self):
        """Test basic DATA encoding."""
        data = b"Hello World"
        packet = TFTPPacket.encode_data(1, data)
        
        self.assertEqual(packet[0:2], b'\x00\x03')  # Opcode 3 (DATA)
        
        opcode, (block_num, decoded_data) = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.DATA)
        self.assertEqual(block_num, 1)
        self.assertEqual(decoded_data, data)
    
    def test_encode_data_max_size(self):
        """Test DATA encoding with maximum size (512 bytes)."""
        data = b'x' * 512
        packet = TFTPPacket.encode_data(1, data)
        
        opcode, (block_num, decoded_data) = TFTPPacket.decode(packet)
        self.assertEqual(len(decoded_data), 512)
    
    def test_encode_data_too_large(self):
        """Test DATA encoding with data > 512 bytes raises error."""
        data = b'x' * 513
        with self.assertRaises(ValueError):
            TFTPPacket.encode_data(1, data)
    
    def test_encode_data_invalid_block(self):
        """Test DATA encoding with invalid block number."""
        data = b"test"
        with self.assertRaises(ValueError):
            TFTPPacket.encode_data(0, data)  # Block 0 is invalid for DATA
        
        with self.assertRaises(ValueError):
            TFTPPacket.encode_data(65536, data)  # Block > 65535


class TestACKEncodingDecoding(unittest.TestCase):
    """Test ACK packet encoding and decoding."""
    
    def test_encode_ack_basic(self):
        """Test basic ACK encoding."""
        packet = TFTPPacket.encode_ack(1)
        
        self.assertEqual(packet[0:2], b'\x00\x04')  # Opcode 4 (ACK)
        self.assertEqual(len(packet), 4)  # ACK is always 4 bytes
        
        opcode, block_num = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.ACK)
        self.assertEqual(block_num, 1)
    
    def test_encode_ack_block_0(self):
        """Test ACK encoding with block 0 (valid for first ACK)."""
        packet = TFTPPacket.encode_ack(0)
        
        opcode, block_num = TFTPPacket.decode(packet)
        self.assertEqual(block_num, 0)
    
    def test_encode_ack_invalid_block(self):
        """Test ACK encoding with invalid block number."""
        with self.assertRaises(ValueError):
            TFTPPacket.encode_ack(-1)
        
        with self.assertRaises(ValueError):
            TFTPPacket.encode_ack(65536)


class TestERROREncodingDecoding(unittest.TestCase):
    """Test ERROR packet encoding and decoding."""
    
    def test_encode_error_basic(self):
        """Test basic ERROR encoding."""
        packet = TFTPPacket.encode_error(ErrorCode.FILE_NOT_FOUND, "File not found")
        
        self.assertEqual(packet[0:2], b'\x00\x05')  # Opcode 5 (ERROR)
        
        opcode, (error_code, error_msg) = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.ERROR)
        self.assertEqual(error_code, ErrorCode.FILE_NOT_FOUND)
        self.assertEqual(error_msg, "File not found")
    
    def test_encode_error_empty_message(self):
        """Test ERROR encoding with empty message."""
        packet = TFTPPacket.encode_error(ErrorCode.ACCESS_VIOLATION, "")
        
        opcode, (error_code, error_msg) = TFTPPacket.decode(packet)
        self.assertEqual(error_code, ErrorCode.ACCESS_VIOLATION)
        self.assertEqual(error_msg, "")  # Empty message is allowed
    
    def test_encode_error_invalid_code(self):
        """Test ERROR encoding with invalid error code."""
        with self.assertRaises(ValueError):
            TFTPPacket.encode_error(99, "Invalid code")


class TestDecodeInvalidPackets(unittest.TestCase):
    """Test decoding of invalid packets."""
    
    def test_decode_empty_data(self):
        """Test decoding empty data raises error."""
        with self.assertRaises(ValueError):
            TFTPPacket.decode(b'')
    
    def test_decode_too_short(self):
        """Test decoding packet with only opcode."""
        with self.assertRaises(ValueError):
            TFTPPacket.decode(b'\x00\x01')  # RRQ opcode but no data
    
    def test_decode_unknown_opcode(self):
        """Test decoding packet with unknown opcode."""
        with self.assertRaises(ValueError):
            TFTPPacket.decode(b'\x00\xFF\x00\x00')  # Opcode 255
    
    def test_decode_invalid_ack(self):
        """Test decoding ACK with wrong size."""
        with self.assertRaises(ValueError):
            TFTPPacket.decode(b'\x00\x04\x00')  # ACK with 3 bytes
    
    def test_decode_invalid_rrq(self):
        """Test decoding RRQ with missing null terminator."""
        with self.assertRaises(ValueError):
            TFTPPacket.decode(b'\x00\x01file.txt')  # No null terminator


class TestIntegration(unittest.TestCase):
    """Integration tests for packet encoding/decoding."""
    
    def test_full_transfer_sequence(self):
        """Test a complete transfer sequence of packets."""
        # 1. Client sends RRQ
        rrq_packet = TFTPPacket.encode_rrq("test.txt")
        opcode, filename = TFTPPacket.decode(rrq_packet)
        self.assertEqual(opcode, Opcode.RRQ)
        self.assertEqual(filename, "test.txt")
        
        # 2. Server sends first DATA block
        data_block1 = b"First block of data"
        data_packet1 = TFTPPacket.encode_data(1, data_block1)
        opcode, (block_num, data) = TFTPPacket.decode(data_packet1)
        self.assertEqual(block_num, 1)
        self.assertEqual(data, data_block1)
        
        # 3. Client sends ACK for block 1
        ack_packet1 = TFTPPacket.encode_ack(1)
        opcode, block_num = TFTPPacket.decode(ack_packet1)
        self.assertEqual(block_num, 1)
        
        # 4. Server sends second DATA block
        data_block2 = b"Second block of data"
        data_packet2 = TFTPPacket.encode_data(2, data_block2)
        opcode, (block_num, data) = TFTPPacket.decode(data_packet2)
        self.assertEqual(block_num, 2)
        self.assertEqual(data, data_block2)
        
        # 5. Client sends ACK for block 2
        ack_packet2 = TFTPPacket.encode_ack(2)
        opcode, block_num = TFTPPacket.decode(ack_packet2)
        self.assertEqual(block_num, 2)
        
        # 6. Server sends final DATA block (< 512 bytes)
        final_data = b"Final block"
        final_packet = TFTPPacket.encode_data(3, final_data)
        opcode, (block_num, data) = TFTPPacket.decode(final_packet)
        self.assertEqual(block_num, 3)
        self.assertEqual(data, final_data)
        
        # 7. Client sends final ACK
        final_ack = TFTPPacket.encode_ack(3)
        opcode, block_num = TFTPPacket.decode(final_ack)
        self.assertEqual(block_num, 3)
    
    def test_error_handling(self):
        """Test error packet handling."""
        # Server sends error
        error_packet = TFTPPacket.encode_error(ErrorCode.FILE_NOT_FOUND, "File missing")
        opcode, (error_code, error_msg) = TFTPPacket.decode(error_packet)
        
        self.assertEqual(error_code, ErrorCode.FILE_NOT_FOUND)
        self.assertEqual(error_msg, "File missing")
        
        # Client receives error and stops


if __name__ == '__main__':
    unittest.main()
