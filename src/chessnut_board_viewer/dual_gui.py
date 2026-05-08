"""Tk two-board viewer for bughouse or side-by-side display."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import font as tkfont

from .board import ChessnutBoard
from .gui import (
    BACKGROUND,
    DARK_SQUARE,
    HIGHLIGHT_DARK,
    HIGHLIGHT_LIGHT,
    LIGHT_SQUARE,
    UNICODE_PIECES,
    _none_board,
    _piece_font_family,
)


class BoardPanel:
    """A single board display panel."""

    def __init__(self, parent, board_num: int, square_size: int):
        self.board_num = board_num
        self.square_size = square_size
        self.board_size = square_size * 8
        self.label_margin = int(square_size * 0.35)

        self.frame = tk.Frame(parent, bg=BACKGROUND, padx=10, pady=10)
        self.frame.pack(side="left", padx=20)

        self.title_var = tk.StringVar(value="Board {}".format(board_num + 1))
        title = tk.Label(
            self.frame,
            textvariable=self.title_var,
            font=("Helvetica", 18, "bold"),
            fg="#FFFFFF",
            bg=BACKGROUND,
        )
        title.pack(pady=(0, 5))

        self.status_var = tk.StringVar(value="Waiting...")
        status = tk.Label(
            self.frame,
            textvariable=self.status_var,
            font=("Helvetica", 12),
            fg="#AAAAAA",
            bg=BACKGROUND,
        )
        status.pack(pady=(0, 10))

        board_frame = tk.Frame(self.frame, bg="#000000", padx=3, pady=3)
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
            self.frame,
            textvariable=self.fen_var,
            font=("Consolas", 9),
            fg="#555555",
            bg=BACKGROUND,
        )
        fen_label.pack(pady=(10, 0))

        font_size = int(square_size * 0.7)
        self.piece_font = tkfont.Font(family=_piece_font_family(parent), size=font_size)

        self.squares = {}
        self.piece_shadows = {}
        self.piece_texts = {}
        self.prev_board = [[None for _ in range(8)] for _ in range(8)]
        self.highlighted_squares = []
        self.draw_board()

    def draw_board(self) -> None:
        offset = self.label_margin
        label_font_size = max(10, int(self.square_size * 0.2))
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

    def update_board(self, fen: str) -> None:
        new_board = _none_board(fen)
        changed = [
            (row, col)
            for row in range(8)
            for col in range(8)
            if new_board[row][col] != self.prev_board[row][col]
        ]

        for row, col in self.highlighted_squares:
            self.reset_square_color(row, col)
        self.highlighted_squares = changed

        for row, col in changed:
            self.highlight_square(row, col)
            self.set_piece(row, col, new_board[row][col])

        self.prev_board = new_board
        self.fen_var.set(fen)


class DualBoardGUI:
    """Main GUI with two boards side by side."""

    def __init__(self, root, fullscreen: bool = True):
        self.root = root
        self.root.title("Chessnut Pro - Dual Board")
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

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        available_width = (screen_width - 100) // 2
        available_height = screen_height - 210
        square_size = max(36, min(available_width // 9, available_height // 9))

        main_frame = tk.Frame(root, bg=BACKGROUND)
        main_frame.place(relx=0.5, rely=0.5, anchor="center")

        title = tk.Label(
            main_frame,
            text="CHESSNUT PRO - DUAL BOARD",
            font=("Helvetica", 28, "bold"),
            fg="#FFFFFF",
            bg=BACKGROUND,
        )
        title.pack(pady=(0, 20))

        boards_frame = tk.Frame(main_frame, bg=BACKGROUND)
        boards_frame.pack()

        self.panels = [
            BoardPanel(boards_frame, 0, square_size),
            BoardPanel(boards_frame, 1, square_size),
        ]

        instructions = tk.Label(
            main_frame,
            text="ESC exits fullscreen | F11 toggles fullscreen | Both boards need yellow USB mode",
            font=("Helvetica", 11),
            fg="#444444",
            bg=BACKGROUND,
        )
        instructions.pack(pady=(20, 0))

        self.boards = [None, None]
        self.running = True
        self.pending_update = [False, False]
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_loop(self) -> None:
        last_fen = ["", ""]
        self._connect_initial_boards()

        while self.running:
            for index in range(2):
                board = self.boards[index]
                if board is None:
                    continue
                if not board.connected:
                    if board.connect():
                        self._set_panel_connected(index, board)
                    else:
                        self.root.after(0, lambda i=index: self.panels[i].status_var.set("Disconnected"))
                        continue

                fen = board.drain_and_get_latest()
                if fen and fen != last_fen[index] and not self.pending_update[index]:
                    last_fen[index] = fen
                    self.pending_update[index] = True
                    panel = self.panels[index]

                    def do_update(panel=panel, value=fen, i=index):
                        panel.update_board(value)
                        self.pending_update[i] = False

                    self.root.after_idle(do_update)

            time.sleep(0.005)

    def _connect_initial_boards(self) -> None:
        try:
            devices = ChessnutBoard.discover()
        except Exception as exc:
            for panel in self.panels:
                self.root.after(0, lambda p=panel, e=exc: p.status_var.set("HID error: {}".format(e)))
            return

        for index, panel in enumerate(self.panels):
            if index >= len(devices):
                self.root.after(0, lambda p=panel: p.status_var.set("Waiting for USB board"))
                continue

            board = ChessnutBoard(device_info=devices[index])
            self.boards[index] = board
            if board.connect():
                self._set_panel_connected(index, board)
            else:
                message = "Connection failed"
                if board.last_error and getattr(board.last_error, "hint", None):
                    message = board.last_error.hint
                self.root.after(0, lambda p=panel, m=message: p.status_var.set(m))

    def _set_panel_connected(self, index: int, board: ChessnutBoard) -> None:
        panel = self.panels[index]
        serial = board.serial or "Board {}".format(index + 1)
        self.root.after(
            0,
            lambda p=panel, s=serial: (
                p.status_var.set("Connected - Live"),
                p.title_var.set("Board: {}".format(s[:20])),
            ),
        )

    def on_close(self) -> None:
        self.running = False
        for board in self.boards:
            if board:
                board.disconnect()
        self.root.destroy()


def main(fullscreen: bool = True) -> int:
    root = tk.Tk()
    DualBoardGUI(root, fullscreen=fullscreen)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
