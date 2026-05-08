# Chessnut HID Protocol Notes

These are the protocol facts this project currently relies on. They were
verified against the EasyLinkSDK files in `sdk/EasyLink.cpp` and the original
Python scripts in this repository.

## Discovery

- Vendor ID: `0x2d80`
- Board data interface usage page: `0xff00`
- Chessnut Pro product IDs are in the `0x81xx` family.
- The EasyLinkSDK checks product families by masking with `product_id & 0xff00`.

## Mode Command

Realtime mode is selected with:

```text
21 01 00
```

Upload mode is:

```text
21 01 01
```

The SDK writes the three-byte command directly. The Python transport tries that
first. If the HID stack rejects it, fallback writes include report-size padding
and a leading zero report ID for stricter macOS behavior.

## Board Reports

Realtime board reports begin with `0x01`.

The 64 squares are nibble-packed into 32 bytes beginning at offset 2. Decoding
mirrors the EasyLinkSDK: ranks are processed top-to-bottom and files are read
right-to-left from the packed data. The resulting string is placement-only FEN,
for example:

```text
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR
```

Piece nibble table:

```text
0 -> empty
1 -> q
2 -> k
3 -> b
4 -> p
5 -> n
6 -> R
7 -> P
8 -> r
9 -> B
10 -> N
11 -> Q
12 -> K
```

Battery reports begin with `0x2a`; byte 2 is the percentage when nonzero.
