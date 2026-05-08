from chessnut_board_viewer.constants import CHESSNUT_VENDOR_ID, PIECES, USAGE_PAGE
from chessnut_board_viewer.protocol import fen_to_board


def device_row(path=b"board-0", product_id=0x8100, usage_page=USAGE_PAGE, serial_number="S1"):
    return {
        "path": path,
        "vendor_id": CHESSNUT_VENDOR_ID,
        "product_id": product_id,
        "serial_number": serial_number,
        "manufacturer_string": "Chessnut",
        "product_string": "Chessnut Pro",
        "usage_page": usage_page,
        "usage": 1,
        "interface_number": 0,
    }


def encode_board_report(fen):
    reverse = {piece: index for index, piece in enumerate(PIECES)}
    data = [0] * 64
    data[0] = 0x01
    data[1] = 0x20
    board = fen_to_board(fen)
    for rank_index, row in enumerate(board):
        for fen_col, piece in enumerate(row):
            piece_index = reverse["0" if piece == "." else piece]
            file_index = 7 - fen_col
            byte_index = (rank_index * 8 + file_index) // 2 + 2
            if file_index % 2 == 0:
                data[byte_index] = (data[byte_index] & 0xF0) | piece_index
            else:
                data[byte_index] = (data[byte_index] & 0x0F) | (piece_index << 4)
    return bytes(data)


class FakeHidDevice:
    def __init__(self, reads=None, write_results=None, serial_number="SERIAL"):
        self.reads = list(reads or [])
        self.write_results = list(write_results or [])
        self.serial_number = serial_number
        self.opened_path = None
        self.closed = False
        self.nonblocking = None
        self.writes = []

    def open_path(self, path):
        if path == b"open-fails":
            raise OSError("cannot open")
        self.opened_path = path

    def set_nonblocking(self, value):
        self.nonblocking = value

    def write(self, data):
        payload = bytes(data)
        self.writes.append(payload)
        if self.write_results:
            result = self.write_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return len(payload)

    def read(self, size, timeout_ms=0):
        if not self.reads:
            return []
        value = self.reads.pop(0)
        if isinstance(value, Exception):
            raise value
        return list(bytes(value)[:size])

    def get_serial_number_string(self):
        return self.serial_number

    def close(self):
        self.closed = True


class FakeHidModule:
    def __init__(self, rows=None, devices=None):
        self.rows = list(rows or [])
        self.devices = list(devices or [])
        self.created_devices = []
        self.__file__ = "fake_hid.py"

    def enumerate(self, vendor_id=0, product_id=0):
        if vendor_id:
            return [row for row in self.rows if row.get("vendor_id") == vendor_id]
        return list(self.rows)

    def device(self):
        device = self.devices.pop(0) if self.devices else FakeHidDevice()
        self.created_devices.append(device)
        return device
