"""Command line entry points for Chessnut board tools."""

from __future__ import annotations

import argparse
import os
import sys
import time

from .board import ChessnutBoard
from .diagnostics import (
    collect_diagnostics,
    format_diagnostics,
    format_smoke_results,
    smoke_test_boards,
)
from .errors import ChessnutError
from .protocol import board_to_ascii


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chessnut-board",
        description="USB HID tools for Chessnut Pro and related boards.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("diagnose", help="show HID setup and device diagnostics")

    list_parser = subparsers.add_parser("list", help="list usable Chessnut HID interfaces")
    list_parser.add_argument("--all", action="store_true", help="show all Chessnut vendor HID rows")

    smoke_parser = subparsers.add_parser("smoke", help="connect and wait for live board reports")
    smoke_parser.add_argument("--boards", type=int, default=1, help="number of boards to connect")
    smoke_parser.add_argument("--timeout", type=float, default=3.0, help="seconds to wait per board")

    watch_parser = subparsers.add_parser("watch", help="print live board states in the terminal")
    watch_parser.add_argument("--board", type=int, default=0, help="zero-based board index")
    watch_parser.add_argument("--poll-ms", type=int, default=10, help="poll interval in milliseconds")
    watch_parser.add_argument("--count", type=int, default=0, help="stop after N FEN changes; 0 means forever")
    watch_parser.add_argument("--once", action="store_true", help="print the first received board state and exit")
    watch_parser.add_argument("--no-clear", action="store_true", help="do not clear the terminal between updates")

    gui_parser = subparsers.add_parser("gui", help="open the single-board Tk viewer")
    gui_parser.add_argument("--board", type=int, default=0, help="zero-based board index")
    gui_parser.add_argument("--windowed", action="store_true", help="start windowed instead of fullscreen")

    dual_parser = subparsers.add_parser("dual", help="open the two-board Tk viewer")
    dual_parser.add_argument("--windowed", action="store_true", help="start windowed instead of fullscreen")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "diagnose"

    if command == "diagnose":
        print(format_diagnostics(collect_diagnostics()))
        return 0
    if command == "list":
        return _list_devices(show_all=args.all)
    if command == "smoke":
        results = smoke_test_boards(board_count=args.boards, timeout_s=args.timeout)
        print(format_smoke_results(results))
        return 0 if all(result.connected and result.fen for result in results) else 1
    if command == "watch":
        return _watch(args)
    if command == "gui":
        from .gui import main as gui_main

        return gui_main(board_index=args.board, fullscreen=not args.windowed)
    if command == "dual":
        from .dual_gui import main as dual_main

        return dual_main(fullscreen=not args.windowed)

    parser.error("unknown command: {}".format(command))
    return 2


def _list_devices(show_all: bool = False) -> int:
    report = collect_diagnostics()
    if not report.hid_available or report.enumeration_error:
        print(format_diagnostics(report))
        return 1

    devices = report.devices if show_all else report.candidates
    if not devices:
        print("No Chessnut board HID interfaces found.")
        print("Run 'chessnut-board diagnose' for setup checks.")
        return 1

    for index, device in enumerate(devices):
        print("[{}] {}".format(index, device.summary()))
        for warning in device.warnings():
            print("    warning: {}".format(warning))
    return 0


def _watch(args) -> int:
    board = ChessnutBoard(board_index=args.board)
    try:
        board.connect_or_raise()
    except ChessnutError as exc:
        print("Could not connect to Chessnut board: {}".format(exc), file=sys.stderr)
        if exc.hint:
            print("Hint: {}".format(exc.hint), file=sys.stderr)
        print("", file=sys.stderr)
        print(format_diagnostics(collect_diagnostics()), file=sys.stderr)
        return 1

    print("Connected to {}.".format(board.label))
    print("Waiting for realtime board reports. Press Ctrl+C to exit.")
    last_fen = None
    updates = 0

    try:
        while True:
            fen = board.get_fen()
            if fen != last_fen:
                last_fen = fen
                updates += 1
                if not args.no_clear:
                    _clear_screen()
                print("CHESSNUT PRO - Live Board")
                print("Device: {}".format(board.label))
                print("FEN: {}".format(fen))
                print(board_to_ascii(board.get_board_array()))
                if args.once or (args.count and updates >= args.count):
                    return 0
            time.sleep(max(0.001, args.poll_ms / 1000.0))
    except KeyboardInterrupt:
        return 0
    finally:
        board.disconnect()


def _clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
