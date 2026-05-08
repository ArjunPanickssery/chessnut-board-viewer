# macOS USB HID Setup and Troubleshooting

This project uses Python `hidapi` bindings and talks directly to the Chessnut
board's USB HID interface. You do not need to build the EasyLinkSDK C++ code for
normal use.

## Install

Prefer Homebrew Python or Python.org Python on macOS. Apple's Command Line
Tools Python can be treated as an Apple platform binary by TCC, which may
prevent macOS from prompting for Input Monitoring when the Chessnut Pro exposes
itself as keyboard-like HID hardware.

```shell
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[hid,dev]"
```

If `hidapi` fails to build on macOS, install build helpers and retry:

```shell
xcode-select --install
brew install hidapi pkg-config
python -m pip install -e ".[hid,dev]"
```

## Expected USB Identity

For a Chessnut Pro connected over USB, diagnostics should show:

- Vendor ID: `0x2d80`
- Product ID family: `0x81xx`
- Usage page: `0xff00`

The EasyLinkSDK lists additional Chessnut families:

- Air: `0x80xx`
- Pro: `0x81xx`
- Air+: `0x82xx`
- Evo: `0x83xx`
- Go: `0x85xx`

The Python discovery code accepts known SDK families and future Chessnut devices
when they expose the expected vendor and usage page.

## Hardware Smoke Test

Run:

```shell
chessnut-board diagnose
chessnut-board smoke --boards 1 --timeout 5
```

Successful output includes a FEN line:

```text
Chessnut hardware smoke test
Board 0 (...): OK
  FEN: 8/8/8/8/8/8/8/8
```

For bughouse with two boards:

```shell
chessnut-board smoke --boards 2 --timeout 5
```

## Common macOS Problems

### `hid module: NOT AVAILABLE`

Install the hardware extra:

```shell
python -m pip install -e ".[hid]"
```

If you are using a virtualenv, make sure it is activated before running the
command and before running `chessnut-board`.

### No Chessnut vendor HID rows

macOS does not see the board at all.

- Use a data-capable USB cable.
- Try another USB-C port or hub.
- Wake the board.
- Check System Report > USB for a device from vendor `0x2d80`.
- Unplug and reconnect after changing board mode.

### Vendor row exists, but no usable board interface

The board may be exposing a different interface than the realtime data HID
interface. The project expects usage page `0xff00`; diagnostics print the usage
page for every Chessnut vendor row so this is visible.

### Open fails

Another process may have the HID interface open, or macOS may be blocking the
process from opening a keyboard-like HID collection. Some Chessnut Pro firmware
enumerates both:

- a generic desktop keyboard-like collection: usage page `0x0001`, usage
  `0x0006`
- the realtime vendor collection: usage page `0xff00`, usage `0xff00`

On macOS, the keyboard-like collection can trigger the Input Monitoring privacy
gate even though this project is trying to read the vendor-defined board data.
If a prompt appears, grant permission to the app running Python, then quit and
restart that app. For example:

- Terminal
- iTerm2
- VS Code
- Codex

- Quit Chessnut apps and old viewer scripts.
- Close browser tabs or integrations that may use WebHID.
- Unplug/replug the board.

If the prompt was denied earlier, open System Settings > Privacy & Security >
Input Monitoring, enable the terminal/editor app, then restart it and retry:

```shell
chessnut-board smoke --boards 1 --timeout 5
```

If the checkbox is already enabled but `open failed` continues, remove the
terminal/editor from Input Monitoring, quit it completely, reopen it, and rerun
the smoke test so macOS creates a fresh permission prompt. For Apple Terminal,
this command resets that one permission entry:

```shell
tccutil reset ListenEvent com.apple.Terminal
```

After resetting, quit and reopen Terminal before running:

```shell
chessnut-board smoke --boards 1 --timeout 5
```

If diagnostics says the virtualenv uses Apple's Command Line Tools Python,
recreate the virtualenv with Homebrew Python:

```shell
deactivate 2>/dev/null || true
rm -rf .venv
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[hid,dev]"
chessnut-board diagnose
chessnut-board smoke --boards 1 --timeout 5
```

### Opens, but no board report arrives

The board is connected but may not be in realtime USB mode.

- Press the board reset/power button until the status LED is yellow.
- Move or lift a piece to force an update.
- Run `chessnut-board smoke --boards 1 --timeout 10`.

## Notes on Permissions

Unlike Linux, macOS usually does not need a udev-style permission rule for HID
devices. If macOS privacy prompts appear, allow Terminal or your Python runner
as appropriate, then unplug/replug the board.
