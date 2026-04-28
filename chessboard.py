#!/usr/bin/env python3
"""
Chessnut Pro USB Board Reader

Reads board state from Chessnut Pro via USB HID.
IMPORTANT: Board must be in "yellow light" mode (press reset/button on board).
"""

import hid
import time
import os
import sys

# Device identifiers
VID = 0x2D80
USAGE_PAGE = 0xFF00

# Piece mapping from Chessnut SDK
PIECES = ['0', 'q', 'k', 'b', 'p', 'n', 'R', 'P', 'r', 'B', 'N', 'Q', 'K']

# Display symbols (uppercase = white, lowercase = black)
SYMBOLS = {
    'K': 'K', 'Q': 'Q', 'R': 'R', 'B': 'B', 'N': 'N', 'P': 'P',
    'k': 'k', 'q': 'q', 'r': 'r', 'b': 'b', 'n': 'n', 'p': 'p',
}


class ChessnutBoard:
    """Interface to Chessnut Pro board via USB HID."""

    def __init__(self):
        self.device = None
        self.current_fen = "8/8/8/8/8/8/8/8"

    def connect(self) -> bool:
        """Connect to the board. Returns True on success."""
        dev_info = None
        for d in hid.enumerate(VID, 0):
            if d.get('usage_page') == USAGE_PAGE:
                dev_info = d
                break

        if not dev_info:
            return False

        try:
            self.device = hid.device()
            self.device.open_path(dev_info['path'])
            self.device.set_nonblocking(True)
            # Send realtime mode command
            self.device.write([0x21, 0x01, 0x00])
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the board."""
        if self.device:
            self.device.close()
            self.device = None

    def read_board(self) -> str | None:
        """Read current board state. Returns FEN string or None."""
        if not self.device:
            return None

        data = self.device.read(64, timeout_ms=5)
        if data and len(data) >= 34 and data[0] == 0x01:
            return self._decode_fen(data)
        return None

    def read_battery(self) -> int:
        """Read battery level. Returns percentage or -1."""
        if not self.device:
            return -1

        data = self.device.read(64, timeout_ms=100)
        if data and len(data) >= 3 and data[0] == 0x2A:
            return data[2]
        return -1

    def _decode_fen(self, data: list) -> str:
        """Decode raw board data to FEN string."""
        fen = ''
        empty = 0

        for rank in range(8):
            for file in range(7, -1, -1):
                byte_idx = (rank * 8 + file) // 2 + 2
                if file % 2 == 0:
                    piece_idx = data[byte_idx] & 0x0F
                else:
                    piece_idx = (data[byte_idx] >> 4) & 0x0F

                piece = PIECES[piece_idx] if piece_idx < len(PIECES) else '0'

                if piece == '0':
                    empty += 1
                else:
                    if empty > 0:
                        fen += str(empty)
                        empty = 0
                    fen += piece

            if empty > 0:
                fen += str(empty)
                empty = 0
            if rank < 7:
                fen += '/'

        return fen

    def get_fen(self) -> str:
        """Get current board state as FEN."""
        new_fen = self.read_board()
        if new_fen:
            self.current_fen = new_fen
        return self.current_fen

    def get_board_array(self) -> list:
        """Convert FEN to 8x8 array."""
        fen = self.current_fen.split()[0]
        board = []
        for rank_str in fen.split('/'):
            row = []
            for ch in rank_str:
                if ch.isdigit():
                    row.extend(['.'] * int(ch))
                else:
                    row.append(ch)
            while len(row) < 8:
                row.append('.')
            board.append(row[:8])
        while len(board) < 8:
            board.append(['.'] * 8)
        return board[:8]


def display_board(board: list):
    """Display the board in ASCII."""
    print("\n     a   b   c   d   e   f   g   h")
    print("   +---+---+---+---+---+---+---+---+")

    for rank_idx, rank in enumerate(board):
        rank_num = 8 - rank_idx
        row = f" {rank_num} |"

        for piece in rank:
            if piece == '.':
                row += "   |"
            else:
                row += f" {piece} |"

        print(row)
        print("   +---+---+---+---+---+---+---+---+")

    print("     a   b   c   d   e   f   g   h\n")


def clear_screen():
    """Clear the terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')


def main():
    print("=" * 50)
    print("      CHESSNUT PRO - USB Board Reader")
    print("=" * 50)
    print()
    print("NOTE: Make sure the board's STATUS LED is YELLOW!")
    print("      (Press the reset/power button if needed)")
    print()

    board = ChessnutBoard()

    print("Connecting to board...")
    if not board.connect():
        print("ERROR: Could not connect to Chessnut Pro!")
        print("- Is the board connected via USB?")
        print("- Is the status LED yellow?")
        sys.exit(1)

    print("Connected! Reading board state...")
    print("(Press Ctrl+C to exit)")
    print()

    last_fen = None

    try:
        while True:
            # Read board state
            fen = board.get_fen()

            if fen != last_fen:
                last_fen = fen
                clear_screen()
                print("CHESSNUT PRO - Live Board")
                print(f"FEN: {fen}")
                display_board(board.get_board_array())
                print("Press Ctrl+C to exit")

            time.sleep(0.01)  # 10ms = 100Hz polling - FAST!

    except KeyboardInterrupt:
        print("\nDisconnecting...")
        board.disconnect()
        print("Goodbye!")


if __name__ == "__main__":
    main()
