# Bluetooth Investigation

## EasyLinkSDK

The public EasyLinkSDK is still centered on USB HID:

- `cl_connect()` constructs `ChessLink::fromHidConnect()`.
- `ChessLink::fromHidConnect()` creates `ChessHidConnect`.
- The README notes that macOS can compile but may not connect, and says BLE is
  not working in that SDK path.

The SDK remains valuable for command and report handling:

- Realtime mode command: `21 01 00`
- Upload mode command: `21 01 01`
- Battery command: `29 01 00`
- Board-state reports start with `01`, then 32 nibble-packed piece bytes.

## BLE References

ChessnutPy and Graham O'Neill's communication notes document the BLE GATT
layout used by Chessnut Air and compatible boards:

- Device names: `Chessnut Air`, `Smart Chess`, and usually other names
  containing `Chessnut`.
- Write characteristic: `1B7E8272-2877-41C3-B46E-CF057C562023`
- Board notify characteristic: `1B7E8262-2877-41C3-B46E-CF057C562023`
- Misc/confirmation notify characteristic:
  `1B7E8273-2877-41C3-B46E-CF057C562023`
- OTB notify characteristic: `1B7E8283-2877-41C3-B46E-CF057C562023`

BLE board reports are 38 bytes:

- `01 24`
- 32 board-state bytes
- 4 trailing bytes, treated here as a little-endian timestamp when present

The 32 board-state bytes match the USB format:

- Stream order is `H8, G8, F8, ... B1, A1`.
- Low nibble is the first square in each pair, high nibble the second.
- Piece map: `0 empty, 1 q, 2 k, 3 b, 4 p, 5 n, 6 R, 7 P, 8 r, 9 B, A N, B Q, C K`.

## Implementation Consequence

This project does not try to make hidapi or EasyLinkSDK open the board on
macOS. The previous USB attempt proved macOS can enumerate the HID interface but
can return `kIOReturnNotPermitted` while opening it. Bluetooth uses a separate
CoreBluetooth privacy path and avoids the keyboard-like HID collection entirely.
