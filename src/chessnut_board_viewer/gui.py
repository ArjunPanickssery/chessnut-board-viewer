"""Tk single-board viewer using the shared Chessnut HID client."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import font as tkfont

from .board import ChessnutBoard
from .protocol import fen_to_board


UNICODE_PIECES = {
    "K": "\u265a",
    "Q": "\u265b",
    "R": "\u265c",
    "B": "\u265d",
    "N": "\u265e",
    "P": "\u265f",
    "k": "\u265a",
    "q": "\u265b",
    "r": "\u265c",
    "b": "\u265d",
    "n": "\u265e",
    "p": "\u265f",
}

LIGHT_SQUARE = "#F0D9B5"
DARK_SQUARE = "#B58863"
HIGHLIGHT_LIGHT = "#CDD26A"
HIGHLIGHT_DARK = "#AAA23A"
BACKGROUND = "#1a1a1a"


class ChessGUI:
    """Graphical chess board display."""

    def __init__(self, root, board_index: int = 0, fullscreen: bool = True):
        self.root = root
        self.board_index = board_index
        self.root.title("Chessnut Pro")
        self.root.configure(bg=BACKGROUND)

        if fullscreen:
            self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda _event: self.root.attributes("-fullscreen", False))
        self.root.bind(
            "<F11>",
            lambda _event: self.root.attributes(
                "-fullscreen",
                not self.root.attributes("-fullscreen"),
            ),
        )

        screen_height = self.root.winfo_screenheight()
        self.square_size = max(42, int((screen_height - 220) / 8))
        self.board_size = self.square_size * 8
        self.label_margin = int(self.square_size * 0.4)

        font_size = int(self.square_size * 0.75)
        self.piece_font = tkfont.Font(family=_piece_font_family(root), size=font_size)

        main_frame = tk.Frame(root, bg=BACKGROUND)
        main_frame.place(relx=0.5, rely=0.5, anchor="center")

        title = tk.Label(
            main_frame,
            text="CHESSNUT PRO",
            font=("Helvetica", 36, "bold"),
            fg="#FFFFFF",
            bg=BACKGROUND,
        )
        title.pack(pady=(0, 10))

        self.status_var = tk.StringVar(value="Connecting...")
        self.status_label = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Helvetica", 16),
            fg="#AAAAAA",
            bg=BACKGROUND,
        )
        self.status_label.pack(pady=(0, 15))

        board_frame = tk.Frame(main_frame, bg="#000000", padx=4, pady=4)
        board_frame.pack()

        canvas_size = self.board_size + self.label_margin * 2
        self.canvas = tk.Canvas(
            board_frame,
            width=canvas_size,
            height=canvas_size,
            bg=BACKGROUND,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.fen_var = tk.StringVar(value="")
        fen_label = tk.Label(
            main_frame,
            textvariable=self.fen_var,
            font=("Consolas", 14),
            fg="#555555",
            bg=BACKGROUND,
        )
        fen_label.pack(pady=(15, 0))

        instructions = tk.Label(
            main_frame,
            text="ESC exits fullscreen | F11 toggles fullscreen",
            font=("Helvetica", 11),
            fg="#444444",
            bg=BACKGROUND,
        )
        instructions.pack(pady=(10, 0))

        self.squares = {}
        self.piece_shadows = {}
        self.piece_texts = {}
        self.prev_board = [[None for _ in range(8)] for _ in range(8)]
        self.highlighted_squares = []

        self.draw_board()

        self.board = ChessnutBoard(board_index=board_index)
        self.running = True
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def draw_board(self) -> None:
        offset = self.label_margin
        label_font_size = max(12, int(self.square_size * 0.22))
        label_font = ("Helvetica", label_font_size, "bold")

        for col in range(8):
            x = offset + col * self.square_size + self.square_size // 2
            self.canvas.create_text(x, offset // 2, text=chr(ord("a") + col), fill="#888888", font=label_font)
            self.canvas.create_text(
                x,
                self.board_size + offset + offset // 2,
                text=chr(ord("a") + col),
                fill="#888888",
                font=label_font,
            )

        for row in range(8):
            y = offset + row * self.square_size + self.square_size // 2
            rank = 8 - row
            self.canvas.create_text(offset // 2, y, text=str(rank), fill="#888888", font=label_font)
            self.canvas.create_text(
                self.board_size + offset + offset // 2,
                y,
                text=str(rank),
                fill="#888888",
                font=label_font,
            )

        for row in range(8):
            for col in range(8):
                x1 = offset + col * self.square_size
                y1 = offset + row * self.square_size
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size
                color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE
                self.squares[(row, col)] = self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

                cx = x1 + self.square_size // 2
                cy = y1 + self.square_size // 2
                offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]
                self.piece_shadows[(row, col)] = [
                    self.canvas.create_text(cx + ox, cy + oy, text="", font=self.piece_font, fill="#000000")
                    for ox, oy in offsets
                ]
                self.piece_texts[(row, col)] = self.canvas.create_text(cx, cy, text="", font=self.piece_font)

    def update_board(self, fen: str) -> None:
        new_board = _none_board(fen)
        changed_squares = [
            (row, col)
            for row in range(8)
            for col in range(8)
            if new_board[row][col] != self.prev_board[row][col]
        ]

        for row, col in self.highlighted_squares:
            self.reset_square_color(row, col)
        self.highlighted_squares = changed_squares
        for row, col in changed_squares:
            self.highlight_square(row, col)
            self.set_piece(row, col, new_board[row][col])

        self.prev_board = new_board

    def highlight_square(self, row: int, col: int) -> None:
        square = self.squares.get((row, col))
        if square:
            color = HIGHLIGHT_LIGHT if (row + col) % 2 == 0 else HIGHLIGHT_DARK
            self.canvas.itemconfig(square, fill=color)

    def reset_square_color(self, row: int, col: int) -> None:
        square = self.squares.get((row, col))
        if square:
            color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE
            self.canvas.itemconfig(square, fill=color)

    def set_piece(self, row: int, col: int, piece) -> None:
        shadows = self.piece_shadows.get((row, col), [])
        piece_text = self.piece_texts.get((row, col))
        if piece and piece in UNICODE_PIECES:
            symbol = UNICODE_PIECES[piece]
            for shadow in shadows:
                self.canvas.itemconfig(shadow, text=symbol, fill="#000000")
            self.canvas.itemconfig(piece_text, text=symbol, fill="#FFD700" if piece.isupper() else "#8B0000")
            return

        for shadow in shadows:
            self.canvas.itemconfig(shadow, text="")
        self.canvas.itemconfig(piece_text, text="")

    def update_loop(self) -> None:
        last_fen = None
        while self.running:
            if not self.board.connected:
                if self.board.connect():
                    self.root.after(0, lambda: self.status_var.set("Connected - Live"))
                else:
                    message = "Not connected - Check USB and yellow LED"
                    if self.board.last_error and getattr(self.board.last_error, "hint", None):
                        message = "Not connected - {}".format(self.board.last_error.hint)
                    self.root.after(0, lambda m=message: self.status_var.set(m))
                    time.sleep(0.5)
                    continue

            fen = self.board.drain_and_get_latest() or self.board.get_fen()
            if fen and fen != last_fen:
                last_fen = fen
                self.root.after_idle(lambda f=fen: self.on_fen_update(f))
            time.sleep(0.01)

    def on_fen_update(self, fen: str) -> None:
        self.update_board(fen)
        self.fen_var.set(fen)

    def on_close(self) -> None:
        self.running = False
        self.board.disconnect()
        self.root.destroy()


def _none_board(fen: str):
    board = fen_to_board(fen)
    return [[None if piece == "." else piece for piece in row] for row in board]


def _piece_font_family(root) -> str:
    families = set(tkfont.families(root))
    for family in ("Apple Symbols", "Segoe UI Symbol", "Arial Unicode MS", "DejaVu Sans"):
        if family in families:
            return family
    return "Helvetica"


def main(board_index: int = 0, fullscreen: bool = True) -> int:
    root = tk.Tk()
    ChessGUI(root, board_index=board_index, fullscreen=fullscreen)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
