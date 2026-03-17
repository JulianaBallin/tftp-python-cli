import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tftp_packets import TFTPPacket, Opcode, ErrorCode


class TestOpcodeEnum(unittest.TestCase):
    """Test Opcode enum values."""
    def test_opcode_values(self):
        self.assertEqual(Opcode.RRQ, 1)
        self.assertEqual(Opcode.WRQ, 2)
        self.assertEqual(Opcode.DATA, 3)
        self.assertEqual(Opcode.ACK, 4)
        self.assertEqual(Opcode.ERROR, 5)


class TestErrorCodeEnum(unittest.TestCase):
    """Test ErrorCode enum values."""
    def test_error_code_values(self):
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
        packet = TFTPPacket.encode_rrq("test.txt")
        self.assertEqual(packet[0:2], b'\x00\x01')
        opcode, filename = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.RRQ)
        self.assertEqual(filename, "test.txt")

    def test_encode_rrq_empty_filename(self):
        with self.assertRaises(ValueError):
            TFTPPacket.encode_rrq("")


class TestWRQEncodingDecoding(unittest.TestCase):
    """Test WRQ packet encoding and decoding."""
    def test_encode_wrq_basic(self):
        packet = TFTPPacket.encode_wrq("upload.txt")
        self.assertEqual(packet[0:2], b'\x00\x02')
        opcode, filename = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.WRQ)
        self.assertEqual(filename, "upload.txt")


class TestDATAEncodingDecoding(unittest.TestCase):
    """Test DATA packet encoding and decoding."""
    def test_encode_data_basic(self):
        data = b"Hello World"
        packet = TFTPPacket.encode_data(1, data)
        self.assertEqual(packet[0:2], b'\x00\x03')
        opcode, (block_num, decoded_data) = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.DATA)
        self.assertEqual(block_num, 1)
        self.assertEqual(decoded_data, data)

    def test_encode_data_too_large(self):
        data = b'x' * 513
        with self.assertRaises(ValueError):
            TFTPPacket.encode_data(1, data)


class TestACKEncodingDecoding(unittest.TestCase):
    """Test ACK packet encoding and decoding."""
    def test_encode_ack_basic(self):
        packet = TFTPPacket.encode_ack(1)
        self.assertEqual(packet[0:2], b'\x00\x04')
        self.assertEqual(len(packet), 4)
        opcode, block_num = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.ACK)
        self.assertEqual(block_num, 1)


class TestERROREncodingDecoding(unittest.TestCase):
    """Test ERROR packet encoding and decoding."""
    def test_encode_error_basic(self):
        packet = TFTPPacket.encode_error(ErrorCode.FILE_NOT_FOUND, "File not found")
        self.assertEqual(packet[0:2], b'\x00\x05')
        opcode, (error_code, error_msg) = TFTPPacket.decode(packet)
        self.assertEqual(opcode, Opcode.ERROR)
        self.assertEqual(error_code, ErrorCode.FILE_NOT_FOUND)
        self.assertEqual(error_msg, "File not found")


if __name__ == '__main__':
    unittest.main()