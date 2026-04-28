#!/usr/bin/env python3
"""
Chessnut Pro DUAL Board Viewer

Shows two chessboards side by side.
Requires: pip install hidapi
"""

import tkinter as tk
from tkinter import font as tkfont
import hid
import threading
import time

# Device identifiers
VID = 0x2D80
USAGE_PAGE = 0xFF00

# Piece mapping from Chessnut SDK
PIECES = ['0', 'q', 'k', 'b', 'p', 'n', 'R', 'P', 'r', 'B', 'N', 'Q', 'K']

# Unicode chess pieces (solid)
UNICODE_PIECES = {
    'K': '\u265A', 'Q': '\u265B', 'R': '\u265C', 'B': '\u265D', 'N': '\u265E', 'P': '\u265F',
    'k': '\u265A', 'q': '\u265B', 'r': '\u265C', 'b': '\u265D', 'n': '\u265E', 'p': '\u265F',
}

# Colors
LIGHT_SQUARE = '#F0D9B5'
DARK_SQUARE = '#B58863'
HIGHLIGHT_LIGHT = '#CDD26A'
HIGHLIGHT_DARK = '#AAA23A'


def find_all_chessnut_boards():
    """Find all connected Chessnut boards."""
    boards = []
    for d in hid.enumerate(VID, 0):
        if d.get('usage_page') == USAGE_PAGE:
            boards.append(d)
    return boards


class ChessnutBoard:
    """USB HID interface to a single Chessnut Pro."""

    def __init__(self, device_path=None):
        self.device = None
        self.device_path = device_path
        self.current_fen = "8/8/8/8/8/8/8/8"
        self.connected = False
        self.serial = "Unknown"

    def connect(self) -> bool:
        if self.device_path:
            try:
                self.device = hid.device()
                self.device.open_path(self.device_path)
                self.device.set_nonblocking(True)
                self.device.write([0x21, 0x01, 0x00])
                self.connected = True
                self.serial = self.device.get_serial_number_string() or "Board"
                return True
            except Exception as e:
                print(f"Connection error: {e}")
                return False
        return False

    def disconnect(self):
        self.connected = False
        if self.device:
            self.device.close()
            self.device = None

    def read_board(self) -> str | None:
        if not self.device:
            return None
        # Use minimal timeout for speed
        data = self.device.read(64, timeout_ms=1)
        if data and len(data) >= 34 and data[0] == 0x01:
            return self._decode_fen(data)
        return None

    def drain_and_get_latest(self) -> str | None:
        """Drain buffer and return latest board state."""
        if not self.device:
            return None
        latest = None
        # Read all pending data (up to 50 reads to drain buffer)
        for _ in range(50):
            data = self.device.read(64, timeout_ms=0)  # Non-blocking
            if not data:
                break
            if len(data) >= 34 and data[0] == 0x01:
                latest = self._decode_fen(data)
        return latest

    def _decode_fen(self, data: list) -> str:
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
        new_fen = self.read_board()
        if new_fen:
            self.current_fen = new_fen
        return self.current_fen


class BoardPanel:
    """A single board display panel."""

    def __init__(self, parent, board_num, square_size):
        self.board_num = board_num
        self.square_size = square_size
        self.board_size = square_size * 8

        # Frame for this board
        self.frame = tk.Frame(parent, bg='#1a1a1a', padx=10, pady=10)
        self.frame.pack(side='left', padx=20)

        # Title
        self.title_var = tk.StringVar(value=f"Board {board_num + 1}")
        title = tk.Label(self.frame, textvariable=self.title_var,
                        font=('Helvetica', 18, 'bold'),
                        fg='#FFFFFF', bg='#1a1a1a')
        title.pack(pady=(0, 5))

        # Status
        self.status_var = tk.StringVar(value="Waiting...")
        status = tk.Label(self.frame, textvariable=self.status_var,
                         font=('Helvetica', 12),
                         fg='#AAAAAA', bg='#1a1a1a')
        status.pack(pady=(0, 10))

        # Canvas
        self.label_margin = int(square_size * 0.35)
        canvas_size = self.board_size + self.label_margin * 2

        board_frame = tk.Frame(self.frame, bg='#000000', padx=3, pady=3)
        board_frame.pack()

        self.canvas = tk.Canvas(board_frame,
                               width=canvas_size,
                               height=canvas_size,
                               bg='#1a1a1a',
                               highlightthickness=0)
        self.canvas.pack()

        # FEN
        self.fen_var = tk.StringVar(value="")
        fen_label = tk.Label(self.frame, textvariable=self.fen_var,
                            font=('Consolas', 9),
                            fg='#555555', bg='#1a1a1a')
        fen_label.pack(pady=(10, 0))

        # Piece font
        font_size = int(square_size * 0.7)
        self.piece_font = tkfont.Font(family='Segoe UI Symbol', size=font_size)

        # Storage
        self.squares = {}
        self.piece_shadows = {}
        self.piece_texts = {}
        self.prev_board = [[None for _ in range(8)] for _ in range(8)]
        self.highlighted_squares = []

        self.draw_board()

    def draw_board(self):
        offset = self.label_margin
        label_font_size = max(10, int(self.square_size * 0.2))
        label_font = ('Helvetica', label_font_size, 'bold')

        # File labels
        for col in range(8):
            x = offset + col * self.square_size + self.square_size // 2
            self.canvas.create_text(x, offset // 2, text=chr(ord('a') + col),
                                   fill='#888888', font=label_font)
            self.canvas.create_text(x, self.board_size + offset + offset // 2,
                                   text=chr(ord('a') + col),
                                   fill='#888888', font=label_font)

        # Rank labels
        for row in range(8):
            y = offset + row * self.square_size + self.square_size // 2
            rank = 8 - row
            self.canvas.create_text(offset // 2, y, text=str(rank),
                                   fill='#888888', font=label_font)
            self.canvas.create_text(self.board_size + offset + offset // 2, y,
                                   text=str(rank),
                                   fill='#888888', font=label_font)

        # Squares
        for row in range(8):
            for col in range(8):
                x1 = offset + col * self.square_size
                y1 = offset + row * self.square_size
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size

                is_light = (row + col) % 2 == 0
                color = LIGHT_SQUARE if is_light else DARK_SQUARE

                square = self.canvas.create_rectangle(x1, y1, x2, y2,
                                                      fill=color, outline='')
                self.squares[(row, col)] = square

                cx = x1 + self.square_size // 2
                cy = y1 + self.square_size // 2

                # Shadows for border
                offsets = [(-2,-2),(-2,2),(2,-2),(2,2),(-2,0),(2,0),(0,-2),(0,2)]
                shadows = []
                for ox, oy in offsets:
                    s = self.canvas.create_text(cx + ox, cy + oy, text='',
                                               font=self.piece_font, fill='#000000')
                    shadows.append(s)
                self.piece_shadows[(row, col)] = shadows

                piece_text = self.canvas.create_text(cx, cy, text='',
                                                     font=self.piece_font)
                self.piece_texts[(row, col)] = piece_text

    def highlight_square(self, row, col):
        square = self.squares.get((row, col))
        if square:
            is_light = (row + col) % 2 == 0
            color = HIGHLIGHT_LIGHT if is_light else HIGHLIGHT_DARK
            self.canvas.itemconfig(square, fill=color)

    def reset_square_color(self, row, col):
        square = self.squares.get((row, col))
        if square:
            is_light = (row + col) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            self.canvas.itemconfig(square, fill=color)

    def set_piece(self, row, col, piece):
        shadows = self.piece_shadows.get((row, col), [])
        piece_text = self.piece_texts.get((row, col))

        if piece and piece in UNICODE_PIECES:
            symbol = UNICODE_PIECES[piece]
            for s in shadows:
                self.canvas.itemconfig(s, text=symbol, fill='#000000')
            if piece.isupper():
                self.canvas.itemconfig(piece_text, text=symbol, fill='#FFD700')
            else:
                self.canvas.itemconfig(piece_text, text=symbol, fill='#8B0000')
        else:
            for s in shadows:
                self.canvas.itemconfig(s, text='')
            self.canvas.itemconfig(piece_text, text='')

    def update_board(self, fen):
        # Parse FEN
        new_board = [[None for _ in range(8)] for _ in range(8)]
        ranks = fen.split('/')
        for row in range(8):
            col = 0
            if row < len(ranks):
                for ch in ranks[row]:
                    if ch.isdigit():
                        col += int(ch)
                    else:
                        if col < 8:
                            new_board[row][col] = ch
                            col += 1

        # Find changes - only update what changed
        changed = []
        for row in range(8):
            for col in range(8):
                if new_board[row][col] != self.prev_board[row][col]:
                    changed.append((row, col))

        # Clear old highlights
        for (row, col) in self.highlighted_squares:
            self.reset_square_color(row, col)

        # New highlights
        self.highlighted_squares = changed
        for (row, col) in changed:
            self.highlight_square(row, col)

        # Only update pieces that changed (not all 64!)
        for (row, col) in changed:
            self.set_piece(row, col, new_board[row][col])

        self.prev_board = new_board
        self.fen_var.set(fen)


class DualBoardGUI:
    """Main GUI with two boards side by side."""

    def __init__(self, root):
        self.root = root
        self.root.title("Chessnut Pro - Dual Board")
        self.root.configure(bg='#1a1a1a')

        # Fullscreen
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        self.root.bind('<F11>', lambda e: self.root.attributes('-fullscreen',
                                            not self.root.attributes('-fullscreen')))

        # Calculate sizes
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Each board gets half the screen width, with margins
        available_width = (screen_width - 100) // 2
        available_height = screen_height - 200

        square_size = min(available_width // 9, available_height // 9)

        # Main container
        main_frame = tk.Frame(root, bg='#1a1a1a')
        main_frame.place(relx=0.5, rely=0.5, anchor='center')

        # Title
        title = tk.Label(main_frame, text="CHESSNUT PRO - DUAL BOARD",
                        font=('Helvetica', 28, 'bold'),
                        fg='#FFFFFF', bg='#1a1a1a')
        title.pack(pady=(0, 20))

        # Board container
        boards_frame = tk.Frame(main_frame, bg='#1a1a1a')
        boards_frame.pack()

        # Create two board panels
        self.panels = [
            BoardPanel(boards_frame, 0, square_size),
            BoardPanel(boards_frame, 1, square_size),
        ]

        # Instructions
        instructions = tk.Label(main_frame,
                               text="ESC = exit fullscreen | F11 = toggle | Both boards need YELLOW LED mode",
                               font=('Helvetica', 11),
                               fg='#444444', bg='#1a1a1a')
        instructions.pack(pady=(20, 0))

        # Board connections
        self.boards = [None, None]
        self.running = True
        self.pending_update = [False, False]  # Prevent update queue buildup

        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_loop(self):
        """Background thread to read both boards - FAST!"""
        # Initial connection attempt
        devices = find_all_chessnut_boards()
        print(f"Found {len(devices)} board(s)")

        last_fen = ["", ""]  # Track last FEN per board

        for i, dev in enumerate(devices[:2]):
            print(f"  Board {i+1}: {dev.get('product_string', 'Unknown')}")
            self.boards[i] = ChessnutBoard(dev['path'])
            if self.boards[i].connect():
                serial = self.boards[i].serial
                panel = self.panels[i]
                self.root.after(0, lambda p=panel, s=serial: (
                    p.status_var.set("Connected - Live"),
                    p.title_var.set(f"Board: {s[:20]}")
                ))
                print(f"  Board {i+1} connected: {serial}")
            else:
                print(f"  Board {i+1} connection FAILED")
                self.root.after(0, lambda p=self.panels[i]: p.status_var.set("Connection failed"))

        while self.running:
            # Read from both boards as fast as possible
            for i in range(2):
                board = self.boards[i]
                if board and board.connected:
                    # Drain buffer and get latest state
                    fen = board.drain_and_get_latest()
                    if fen and fen != last_fen[i] and not self.pending_update[i]:
                        last_fen[i] = fen
                        self.pending_update[i] = True
                        panel = self.panels[i]
                        idx = i
                        # Schedule GUI update - mark complete when done
                        def do_update(p=panel, f=fen, j=idx):
                            p.update_board(f)
                            self.pending_update[j] = False
                        self.root.after_idle(do_update)

            # Minimal sleep - just yield to other threads
            time.sleep(0.001)

    def on_close(self):
        self.running = False
        for board in self.boards:
            if board:
                board.disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = DualBoardGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
