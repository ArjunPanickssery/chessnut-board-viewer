from chessnut_board_viewer.board import ChessnutBoard
from chessnut_board_viewer.constants import BATTERY_REQUEST_COMMAND, REALTIME_MODE_COMMAND
from chessnut_board_viewer.protocol import EMPTY_FEN

from .fakes import FakeHidDevice, FakeHidModule, device_row, encode_board_report


def test_board_connects_switches_realtime_and_reads_fen():
    fen = "8/8/8/3K4/8/8/8/8"
    fake_device = FakeHidDevice(reads=[encode_board_report(fen)], serial_number="PRO-1")
    hid = FakeHidModule(rows=[device_row(path=b"board", serial_number="PRO-1")], devices=[fake_device])
    board = ChessnutBoard(hid_module=hid)

    assert board.connect()
    assert board.serial == "PRO-1"
    assert fake_device.writes[0] == REALTIME_MODE_COMMAND
    assert board.read_board() == fen
    assert board.current_fen == fen


def test_board_connect_returns_false_and_preserves_last_error():
    hid = FakeHidModule(rows=[])
    board = ChessnutBoard(hid_module=hid)

    assert not board.connect()
    assert board.last_error is not None
    assert "No Chessnut board found" in str(board.last_error)


def test_board_drain_ignores_battery_and_returns_latest_fen():
    first = EMPTY_FEN
    latest = "8/8/8/8/4Q3/8/8/8"
    fake_device = FakeHidDevice(
        reads=[
            encode_board_report(first),
            bytes([0x2A, 0x01, 91]),
            encode_board_report(latest),
        ]
    )
    hid = FakeHidModule(rows=[device_row(path=b"board")], devices=[fake_device])
    board = ChessnutBoard(hid_module=hid)
    assert board.connect()

    assert board.drain_and_get_latest() == latest
    assert board.last_battery_percent == 91
    assert board.current_fen == latest


def test_board_read_battery_sends_request_and_keeps_board_reports():
    fen = "8/8/8/8/8/8/3n4/8"
    fake_device = FakeHidDevice(
        reads=[
            encode_board_report(fen),
            bytes([0x2A, 0x01, 64]),
        ]
    )
    hid = FakeHidModule(rows=[device_row(path=b"board")], devices=[fake_device])
    board = ChessnutBoard(hid_module=hid)
    assert board.connect()

    assert board.read_battery(timeout_s=0.1) == 64
    assert fake_device.writes[1] == BATTERY_REQUEST_COMMAND
    assert board.current_fen == fen


def test_board_index_selects_second_connected_board():
    rows = [
        device_row(path=b"board-0", serial_number="A"),
        device_row(path=b"board-1", serial_number="B"),
    ]
    second_device = FakeHidDevice(serial_number="B")
    hid = FakeHidModule(rows=rows, devices=[second_device])
    board = ChessnutBoard(board_index=1, hid_module=hid)

    assert board.connect()
    assert second_device.opened_path == b"board-1"
    assert board.serial == "B"
