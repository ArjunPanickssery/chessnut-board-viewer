"""Chessnut USB HID board reader and viewer helpers."""

from .board import ChessnutBoard
from .constants import (
    CHESSNUT_VENDOR_ID,
    PRO_PRODUCT_FAMILY,
    REALTIME_MODE_COMMAND,
    USAGE_PAGE,
)
from .hid_transport import HidDeviceInfo, find_chessnut_boards
from .protocol import decode_board_report, fen_to_board

__all__ = [
    "CHESSNUT_VENDOR_ID",
    "PRO_PRODUCT_FAMILY",
    "REALTIME_MODE_COMMAND",
    "USAGE_PAGE",
    "ChessnutBoard",
    "HidDeviceInfo",
    "decode_board_report",
    "fen_to_board",
    "find_chessnut_boards",
]

__version__ = "0.2.0"
