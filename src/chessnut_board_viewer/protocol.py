"""Chessnut report decoding and board representation helpers."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from .constants import (
    BATTERY_REPORT_ID,
    BOARD_REPORT_ID,
    MIN_BOARD_REPORT_LENGTH,
    PIECES,
)
from .errors import ProtocolError


EMPTY_FEN = "8/8/8/8/8/8/8/8"


def normalize_report(data: Sequence[int]) -> bytes:
    """Return a bytes report, tolerating a leading zero report ID on macOS."""

    report = bytes(data or [])
    if len(report) >= 2 and report[0] == 0x00 and report[1] in (BOARD_REPORT_ID, BATTERY_REPORT_ID):
        return report[1:]
    return report


def is_board_report(data: Sequence[int]) -> bool:
    report = normalize_report(data)
    return len(report) >= MIN_BOARD_REPORT_LENGTH and report[0] == BOARD_REPORT_ID


def decode_board_report(data: Sequence[int]) -> str:
    """Decode a realtime board-state HID report into placement-only FEN.

    Chessnut realtime reports start with ``0x01`` and then store the 64 board
    squares in 32 nibble-packed bytes beginning at offset 2. The EasyLinkSDK
    iterates ranks top-to-bottom and files right-to-left; this implementation
    intentionally mirrors that behavior so existing viewer orientation is
    preserved.
    """

    report = normalize_report(data)
    if len(report) < MIN_BOARD_REPORT_LENGTH or report[0] != BOARD_REPORT_ID:
        raise ProtocolError(
            "HID report is not a Chessnut realtime board report",
            hint="Expected a report beginning with 0x01 and containing at least 34 bytes.",
        )

    fen_parts = []
    for rank in range(8):
        empty = 0
        rank_fen = []
        for file_index in range(7, -1, -1):
            byte_index = (rank * 8 + file_index) // 2 + 2
            packed = report[byte_index]
            if file_index % 2 == 0:
                piece_index = packed & 0x0F
            else:
                piece_index = (packed >> 4) & 0x0F

            piece = PIECES[piece_index] if piece_index < len(PIECES) else "0"
            if piece == "0":
                empty += 1
                continue

            if empty:
                rank_fen.append(str(empty))
                empty = 0
            rank_fen.append(piece)

        if empty:
            rank_fen.append(str(empty))
        fen_parts.append("".join(rank_fen) or "8")

    return "/".join(fen_parts)


def decode_battery_report(data: Sequence[int]) -> Optional[int]:
    """Return battery percentage from a battery report, or ``None``."""

    report = normalize_report(data)
    if len(report) >= 3 and report[0] == BATTERY_REPORT_ID:
        return int(report[2])
    return None


def fen_to_board(fen: str) -> List[List[str]]:
    """Convert placement-only or full FEN into an 8x8 array using ``.`` empties."""

    placement = (fen or EMPTY_FEN).split()[0]
    board = []
    for rank_text in placement.split("/")[:8]:
        row = []
        for char in rank_text:
            if char.isdigit():
                row.extend(["."] * int(char))
            else:
                row.append(char)
        row.extend(["."] * (8 - len(row)))
        board.append(row[:8])

    while len(board) < 8:
        board.append(["."] * 8)
    return board[:8]


def board_to_ascii(board: Iterable[Iterable[str]]) -> str:
    """Render an 8x8 board array as a terminal-friendly text board."""

    lines = ["", "     a   b   c   d   e   f   g   h", "   +---+---+---+---+---+---+---+---+"]
    for rank_index, rank in enumerate(board):
        rank_number = 8 - rank_index
        row = " {} |".format(rank_number)
        for piece in list(rank)[:8]:
            row += " {} |".format(" " if piece == "." else piece)
        lines.append(row)
        lines.append("   +---+---+---+---+---+---+---+---+")
    lines.append("     a   b   c   d   e   f   g   h")
    lines.append("")
    return "\n".join(lines)
