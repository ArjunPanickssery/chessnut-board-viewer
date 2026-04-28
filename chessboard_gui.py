#!/usr/bin/env python3
"""
Chessnut Pro GUI Board Viewer

A nice graphical display for the Chessnut Pro board.
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

# Unicode chess pieces (using filled/solid symbols for both colors)
UNICODE_PIECES = {
    'K': '\u265A', 'Q': '\u265B', 'R': '\u265C', 'B': '\u265D', 'N': '\u265E', 'P': '\u265F',
    'k': '\u265A', 'q': '\u265B', 'r': '\u265C', 'b': '\u265D', 'n': '\u265E', 'p': '\u265F',
}

# Colors
LIGHT_SQUARE = '#F0D9B5'
DARK_SQUARE = '#B58863'
HIGHLIGHT_LIGHT = '#CDD26A'  # Yellow-green highlight for light squares
HIGHLIGHT_DARK = '#AAA23A'   # Darker yellow-green for dark squares


class ChessnutBoard:
    """USB HID interface to Chessnut Pro."""

    def __init__(self):
        self.device = None
        self.current_fen = "8/8/8/8/8/8/8/8"
        self.connected = False

    def connect(self) -> bool:
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
            self.device.write([0x21, 0x01, 0x00])
            self.connected = True
            return True
        except Exception:
            return False

    def disconnect(self):
        self.connected = False
        if self.device:
            self.device.close()
            self.device = None

    def read_board(self) -> str | None:
        if not self.device:
            return None

        # Read with minimal timeout for speed
        data = self.device.read(64, timeout_ms=5)
        if data and len(data) >= 34 and data[0] == 0x01:
            return self._decode_fen(data)
        return None

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


class ChessGUI:
    """Graphical chess board display."""

    def __init__(self, root):
        self.root = root
        self.root.title("Chessnut Pro")
        self.root.configure(bg='#1a1a1a')

        # Make fullscreen
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        self.root.bind('<F11>', lambda e: self.root.attributes('-fullscreen',
                                            not self.root.attributes('-fullscreen')))

        # Calculate square size based on screen height
        screen_height = self.root.winfo_screenheight()
        self.square_size = int((screen_height - 200) / 8)
        self.board_size = self.square_size * 8

        # Chess piece font - scale with square size
        font_size = int(self.square_size * 0.75)
        self.piece_font = tkfont.Font(family='Segoe UI Symbol', size=font_size)

        # Main frame - centered
        main_frame = tk.Frame(root, bg='#1a1a1a')
        main_frame.place(relx=0.5, rely=0.5, anchor='center')

        # Title
        title = tk.Label(main_frame, text="CHESSNUT PRO",
                        font=('Helvetica', 36, 'bold'),
                        fg='#FFFFFF', bg='#1a1a1a')
        title.pack(pady=(0, 10))

        # Status
        self.status_var = tk.StringVar(value="Connecting...")
        self.status_label = tk.Label(main_frame, textvariable=self.status_var,
                                     font=('Helvetica', 16),
                                     fg='#AAAAAA', bg='#1a1a1a')
        self.status_label.pack(pady=(0, 15))

        # Board frame with border
        board_frame = tk.Frame(main_frame, bg='#000000', padx=4, pady=4)
        board_frame.pack()

        # Canvas for the board
        label_margin = int(self.square_size * 0.4)
        canvas_size = self.board_size + label_margin * 2
        self.canvas = tk.Canvas(board_frame,
                               width=canvas_size,
                               height=canvas_size,
                               bg='#1a1a1a',
                               highlightthickness=0)
        self.canvas.pack()

        # FEN display
        self.fen_var = tk.StringVar(value="")
        fen_label = tk.Label(main_frame, textvariable=self.fen_var,
                            font=('Consolas', 14),
                            fg='#555555', bg='#1a1a1a')
        fen_label.pack(pady=(15, 0))

        # Instructions
        instructions = tk.Label(main_frame, text="Press ESC to exit fullscreen, F11 to toggle",
                               font=('Helvetica', 11),
                               fg='#444444', bg='#1a1a1a')
        instructions.pack(pady=(10, 0))

        # Store label margin for drawing
        self.label_margin = label_margin

        # Store square and piece references
        self.squares = {}
        self.piece_shadows = {}
        self.piece_texts = {}

        # Track previous board state for move highlighting
        self.prev_board = [[None for _ in range(8)] for _ in range(8)]
        self.highlighted_squares = []

        # Draw the board
        self.draw_board()

        # Board connection
        self.board = ChessnutBoard()
        self.running = True

        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def draw_board(self):
        """Draw the chess board."""
        offset = self.label_margin
        label_font_size = max(12, int(self.square_size * 0.22))
        label_font = ('Helvetica', label_font_size, 'bold')

        # Draw file labels (a-h)
        for col in range(8):
            x = offset + col * self.square_size + self.square_size // 2
            self.canvas.create_text(x, offset // 2, text=chr(ord('a') + col),
                                   fill='#888888', font=label_font)
            self.canvas.create_text(x, self.board_size + offset + offset // 2,
                                   text=chr(ord('a') + col),
                                   fill='#888888', font=label_font)

        # Draw rank labels (1-8)
        for row in range(8):
            y = offset + row * self.square_size + self.square_size // 2
            rank = 8 - row
            self.canvas.create_text(offset // 2, y, text=str(rank),
                                   fill='#888888', font=label_font)
            self.canvas.create_text(self.board_size + offset + offset // 2, y,
                                   text=str(rank),
                                   fill='#888888', font=label_font)

        # Draw squares
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

                # Center of square
                cx = x1 + self.square_size // 2
                cy = y1 + self.square_size // 2

                # Shadows for thick black border (optimized for speed)
                offsets = [(-2,-2),(-2,2),(2,-2),(2,2),(-2,0),(2,0),(0,-2),(0,2)]
                shadows = []
                for ox, oy in offsets:
                    s = self.canvas.create_text(cx + ox, cy + oy, text='',
                                               font=self.piece_font, fill='#000000')
                    shadows.append(s)
                self.piece_shadows[(row, col)] = shadows

                # Main piece text
                piece_text = self.canvas.create_text(cx, cy, text='',
                                                     font=self.piece_font)
                self.piece_texts[(row, col)] = piece_text

    def update_board(self, fen: str):
        """Update the board display from FEN."""
        # Parse FEN into 8x8 array
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

        # Find changed squares for highlighting
        changed_squares = []
        for row in range(8):
            for col in range(8):
                if new_board[row][col] != self.prev_board[row][col]:
                    changed_squares.append((row, col))

        # Clear previous highlights
        for (row, col) in self.highlighted_squares:
            self.reset_square_color(row, col)

        # Apply new highlights
        self.highlighted_squares = changed_squares
        for (row, col) in changed_squares:
            self.highlight_square(row, col)

        # Update pieces on display
        for row in range(8):
            for col in range(8):
                self.set_piece(row, col, new_board[row][col])

        # Save current board as previous
        self.prev_board = new_board

    def highlight_square(self, row: int, col: int):
        """Highlight a square (for showing moves)."""
        square = self.squares.get((row, col))
        if square:
            is_light = (row + col) % 2 == 0
            color = HIGHLIGHT_LIGHT if is_light else HIGHLIGHT_DARK
            self.canvas.itemconfig(square, fill=color)

    def reset_square_color(self, row: int, col: int):
        """Reset a square to its normal color."""
        square = self.squares.get((row, col))
        if square:
            is_light = (row + col) % 2 == 0
            color = LIGHT_SQUARE if is_light else DARK_SQUARE
            self.canvas.itemconfig(square, fill=color)

    def set_piece(self, row: int, col: int, piece: str | None):
        """Set a piece on the board."""
        shadows = self.piece_shadows.get((row, col), [])
        piece_text = self.piece_texts.get((row, col))

        if piece and piece in UNICODE_PIECES:
            symbol = UNICODE_PIECES[piece]

            # Set all shadow layers for thick border
            for s in shadows:
                self.canvas.itemconfig(s, text=symbol, fill='#000000')

            if piece.isupper():
                # White piece - bright yellow/gold
                self.canvas.itemconfig(piece_text, text=symbol, fill='#FFD700')
            else:
                # Black piece - dark red/maroon
                self.canvas.itemconfig(piece_text, text=symbol, fill='#8B0000')
        else:
            for s in shadows:
                self.canvas.itemconfig(s, text='')
            self.canvas.itemconfig(piece_text, text='')

    def update_loop(self):
        """Background thread to read board state - FAST!"""
        if self.board.connect():
            self.root.after(0, lambda: self.status_var.set("Connected - Live"))
        else:
            self.root.after(0, lambda: self.status_var.set("Not connected - Check USB & yellow LED"))

        last_fen = None

        while self.running:
            if self.board.connected:
                # Read multiple times per cycle for faster response
                for _ in range(10):
                    fen = self.board.get_fen()
                    if fen and fen != last_fen:
                        last_fen = fen
                        self.root.after_idle(lambda f=fen: self.on_fen_update(f))
                        break
            else:
                if self.board.connect():
                    self.root.after(0, lambda: self.status_var.set("Connected - Live"))
                time.sleep(0.1)
                continue

            time.sleep(0.005)  # 5ms = 200Hz polling

    def on_fen_update(self, fen: str):
        """Called when FEN updates (in main thread)."""
        self.update_board(fen)
        self.fen_var.set(fen)

    def on_close(self):
        """Handle window close."""
        self.running = False
        self.board.disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = ChessGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
