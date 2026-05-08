#!/usr/bin/env python3
"""Compatibility wrapper for the terminal Chessnut board viewer."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from chessnut_board_viewer.board import ChessnutBoard  # noqa: E402
from chessnut_board_viewer.cli import main as cli_main  # noqa: E402
from chessnut_board_viewer.protocol import board_to_ascii  # noqa: E402


def display_board(board):
    """Display an 8x8 board array in ASCII."""

    print(board_to_ascii(board))


def clear_screen():
    """Clear the terminal."""

    os.system("cls" if os.name == "nt" else "clear")


def main(argv=None):
    return cli_main(["watch"] + list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
