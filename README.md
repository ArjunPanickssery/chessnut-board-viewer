# Chessnut Board Viewer

USB HID tools and Tk viewers for Chessnut electronic chessboards, focused on
making a Chessnut Pro reliable on macOS while preserving the old Windows-style
viewer workflow.

The original repository carried a copy of Chessnut's EasyLinkSDK C/C++ code.
That SDK remains in `sdk/` and `thirdparty/` as a protocol reference, but the
Python tools now talk directly to the board through Python's `hid` module.

## What Works

- Finds Chessnut HID devices with vendor `0x2d80`.
- Prefers Chessnut Pro product-family IDs `0x81xx`.
- Uses the board data HID interface at usage page `0xff00`.
- Opens boards by HID path, which allows two connected boards to be addressed
  separately.
- Sends realtime mode command `21 01 00`.
- Reads 64-byte HID reports and decodes `01 ...` board-state reports into FEN.
- Provides one-board terminal, one-board GUI, and two-board GUI entry points.
- Provides diagnostics and mocked tests that do not need physical hardware.

## macOS Quick Start

```shell
cd /Users/arjun/arjun/code/chessnut
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[hid,dev]"
```

Connect the Chessnut Pro with a data-capable USB cable, wake it, and put it in
yellow status LED USB/EasyLink mode.

```shell
chessnut-board diagnose
chessnut-board smoke --boards 1 --timeout 5
chessnut-board watch
chessnut-board gui
```

For two connected boards:

```shell
chessnut-board smoke --boards 2 --timeout 5
chessnut-board dual
```

The old script names still work after installing the project:

```shell
python chessboard.py
python chessboard_gui.py
python chessboard_dual.py
```

## Commands

- `chessnut-board diagnose`: prints Python, `hid`, VID/PID/usage-page, and setup
  hints.
- `chessnut-board list`: lists usable Chessnut board HID interfaces.
- `chessnut-board smoke --boards N`: opens one or two boards, switches realtime
  mode, and waits for live board reports.
- `chessnut-board watch`: prints live FEN and an ASCII board in the terminal.
- `chessnut-board gui`: opens the single-board Tk viewer.
- `chessnut-board dual`: opens the two-board Tk viewer.

## Development

The Python package lives in `src/chessnut_board_viewer/`.

```shell
source .venv/bin/activate
python -m pytest
python -m chessnut_board_viewer diagnose
```

Tests use mocked HID devices, so they validate protocol decoding, discovery,
write fallbacks, diagnostics, battery reports, and two-board selection without a
physical board.

## Troubleshooting

Start with:

```shell
chessnut-board diagnose
chessnut-board smoke --boards 1 --timeout 5
```

If no board appears:

- Use a data-capable USB cable. Many USB-C cables are charge-only.
- Check Apple menu > About This Mac > More Info > System Report > USB.
- Confirm the board is awake and showing the yellow status LED.
- Quit Chessnut apps, browser integrations, or older viewers that may already
  have the HID interface open.
- Unplug/replug the board after changing mode.

If the board opens but no FEN arrives:

- Move or lift a piece to force a realtime update.
- Press the board reset/power button until the status LED is yellow.
- Run `chessnut-board smoke --boards 1 --timeout 10` and copy the output into a
  bug report.

More detailed macOS notes are in [docs/macos-usb.md](docs/macos-usb.md).
Protocol assumptions are in [docs/protocol.md](docs/protocol.md).
