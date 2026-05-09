# macOS Bluetooth Setup And Troubleshooting

## Basic Flow

```sh
make
make test
./scripts/chessnut-ble-app scan --timeout 8
./scripts/chessnut-ble-app watch --boards 1 --timeout 30
```

For two boards:

```sh
./scripts/chessnut-ble-app watch --boards 2 --timeout 30
```

Viewer UI:

```sh
./scripts/chessnut-viewer --boards 1
```

Demo viewer without hardware:

```sh
./scripts/chessnut-viewer --demo
```

The raw `./build/chessnut-ble` binary is useful from launchers that already
carry a Bluetooth usage description, such as VS Code. For Apple's Terminal,
iTerm, and Codex, the wrapper script is safer because it launches the signed
`build/ChessnutBLE.app` bundle and relays its output back into your shell.

## Board State

Use Bluetooth mode rather than USB/EasyLink cable mode. If the board was just
used over USB or by a mobile app, power-cycle it before scanning. BLE boards
often stay connected to the last app that used them; only one central can own
the active GATT connection reliably.

## macOS Permissions

CoreBluetooth permission is separate from the USB Input Monitoring issue.

If macOS prompts for Bluetooth access, grant it to:

- Chessnut BLE

If you intentionally run the raw binary instead of the app wrapper, grant it to
the app running the command:

- Terminal
- iTerm
- VS Code
- Codex

Then quit and reopen that app. If permission is stale, remove the app from
System Settings > Privacy & Security > Bluetooth, run the scan again, and accept
the prompt.

## Diagnostics

Show only Chessnut-like devices:

```sh
./scripts/chessnut-ble-app scan --timeout 8
```

Show all BLE advertisements:

```sh
./scripts/chessnut-ble-app scan --timeout 8 --all
```

Use verbose GATT tracing:

```sh
./scripts/chessnut-ble-app probe --boards 1 --timeout 30 --verbose
```

Show every realtime report, including unchanged positions:

```sh
./scripts/chessnut-ble-app watch --boards 1 --timeout 30 --all-reports
```

Filter by advertised name:

```sh
./scripts/chessnut-ble-app watch --name Chessnut --timeout 30
```

## Interpreting Failures

`Bluetooth is not authorized`

Grant Bluetooth privacy permission to the launcher app and restart it.

`No Chessnut BLE boards were discovered`

The board is off, in the wrong mode, already connected to another app, too far
away, or not advertising under a recognized name. Try `scan --all`.

`Connected, but no board-state notifications arrived`

The CLI connected but did not receive reports after sending `21 01 00`. Run
`probe --verbose`; if the discovered UUIDs differ from the documented UUIDs,
the transport needs a board-specific characteristic update.

## Useful Smoke Tests

Starting-position FEN should print as:

```text
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR
```

LED command:

```sh
./scripts/chessnut-ble-app led e2 e4 --hold 1500
```

This should light E2 and E4 briefly, then turn LEDs off.

## Visual Assets

The web viewer uses the CBurnett SVG pieces copied from the local Gravity Chess
project. Those assets come from the Lichess piece set credited to Colin M.L.
Burnett under GPLv2+ in that project.
