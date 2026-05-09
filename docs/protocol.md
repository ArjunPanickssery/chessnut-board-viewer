# Chessnut Protocol Notes

## Realtime Mode

Send:

```text
21 01 00
```

BLE confirmation/misc notifications may include:

```text
23 01 00
21 01 00
```

## Board Reports

USB/HID:

```text
01 3d <32 board bytes> <padding/extra bytes>
```

BLE:

```text
01 24 <32 board bytes> <4 trailing bytes>
```

The project accepts either shape in the parser so shared tests can validate the
common board-state logic.

## Starting Position

The starting position board bytes are:

```text
58 23 31 85 44 44 44 44 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 77 77 77 77 a6 c9 9b 6a
```

Decoded FEN:

```text
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR
```

## LED Commands

```text
0a 08 <R8> <R7> <R6> <R5> <R4> <R3> <R2> <R1>
```

File bits in each rank byte are:

```text
A=128 B=64 C=32 D=16 E=8 F=4 G=2 H=1
```

For E2 and E4:

```text
0a 08 00 00 00 00 08 00 08 00
```
