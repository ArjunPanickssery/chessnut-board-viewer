#!/usr/bin/env python3
"""Compatibility wrapper for the single-board Chessnut GUI viewer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from chessnut_board_viewer.cli import main as cli_main  # noqa: E402
from chessnut_board_viewer.gui import ChessGUI  # noqa: E402,F401


def main(argv=None):
    return cli_main(["gui"] + list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
