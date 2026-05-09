# Chessnut BLE Tools for macOS

This repository is a fresh Bluetooth-first experiment for Chessnut boards on
macOS. The previous USB/HID attempt is preserved in git as:

```sh
git show c949ca9
```

## What This Builds

- A plain C protocol library for Chessnut board reports, FEN decoding, battery
  packets, and LED commands.
- A macOS CoreBluetooth transport exposed through a C API.
- A CLI named `chessnut-ble` for scanning, probing, watching one or two boards,
  and sending a simple LED command.
- A local web viewer using the same CBurnett SVG pieces as the Gravity Chess
  board at `/Users/arjun/arjun/code/gravity_chess`.
- Unit tests that exercise the protocol without physical hardware.

The public Chessnut EasyLinkSDK is useful as a protocol reference, but its
current connection path is HID-only. Its `cl_connect()` path constructs
`ChessLink::fromHidConnect()`, so this project does not reuse that transport.
Instead, it reuses the same command/report semantics over BLE GATT.

## Build And Test

Requirements:

- macOS
- Xcode Command Line Tools
- Bluetooth enabled

```sh
make clean
make
make test
```

The CLI will be built at:

```sh
./build/chessnut-ble
```

macOS may attribute Bluetooth permission to the app that launched the command,
not to the command-line binary itself. For normal Terminal use, prefer the app
wrapper script:

```sh
./scripts/chessnut-ble-app scan --timeout 8
```

## Hardware Smoke Tests

First scan:

```sh
./scripts/chessnut-ble-app scan --timeout 8
```

If you do not see a board, confirm general Bluetooth scanning:

```sh
./scripts/chessnut-ble-app scan --timeout 8 --all
```

Watch one board:

```sh
./scripts/chessnut-ble-app watch --boards 1 --timeout 30
```

Normal `watch` output prints only changed positions. For raw realtime reports:

```sh
./scripts/chessnut-ble-app watch --boards 1 --timeout 30 --all-reports
```

Watch two boards for bughouse-style use:

```sh
./scripts/chessnut-ble-app watch --boards 2 --timeout 30
```

Verbose probe:

```sh
./scripts/chessnut-ble-app probe --boards 1 --timeout 30 --verbose
```

LED test:

```sh
./scripts/chessnut-ble-app led e2 e4 --hold 1500
```

Viewer UI:

```sh
./scripts/chessnut-viewer --boards 1
```

Two-board viewer:

```sh
./scripts/chessnut-viewer --boards 2
```

The viewer starts a local web server and opens your browser. It launches
`ChessnutBLE.app` behind the scenes so Bluetooth permission remains attached to
the signed app wrapper.

## macOS Bluetooth Setup

1. Turn on the Chessnut board and put it in Bluetooth mode.
2. Close the official Chessnut app, EasyLink experiments, browser tabs using
   Web Bluetooth, and any previous viewer process.
3. Run `./scripts/chessnut-ble-app scan --timeout 8`.
4. If macOS prompts for Bluetooth permission, grant it to `Chessnut BLE`.
5. Restart the command after changing Bluetooth privacy permission.

You usually should not manually pair a BLE GATT device in macOS Bluetooth
settings. The CLI scans and connects through CoreBluetooth directly.

More setup and troubleshooting notes are in
[`docs/bluetooth-setup.md`](docs/bluetooth-setup.md).
