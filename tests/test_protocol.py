import pytest

from chessnut_board_viewer.errors import ProtocolError
from chessnut_board_viewer.protocol import (
    EMPTY_FEN,
    decode_battery_report,
    decode_board_report,
    fen_to_board,
    is_board_report,
)

from .fakes import encode_board_report


def test_decode_empty_board_report():
    assert decode_board_report(encode_board_report(EMPTY_FEN)) == EMPTY_FEN


def test_decode_starting_position_report():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    assert decode_board_report(encode_board_report(fen)) == fen


def test_decode_tolerates_leading_zero_report_id():
    fen = "8/8/8/3K4/8/8/8/8"
    report = bytes([0]) + encode_board_report(fen)
    assert is_board_report(report)
    assert decode_board_report(report) == fen


def test_invalid_board_report_raises_protocol_error():
    with pytest.raises(ProtocolError):
        decode_board_report([0x02, 0x00, 0x00])


def test_decode_battery_report():
    assert decode_battery_report([0x2A, 0x01, 87]) == 87
    assert decode_battery_report([0x00, 0x2A, 0x01, 55]) == 55
    assert decode_battery_report([0x01, 0x20]) is None


def test_fen_to_board_accepts_full_fen_and_pads_bad_rows():
    board = fen_to_board("8/8/8/3Q4/8/8/8/8 w - - 0 1")
    assert board[3][3] == "Q"
    assert board[0] == ["."] * 8
    assert len(board) == 8
    assert all(len(row) == 8 for row in board)
