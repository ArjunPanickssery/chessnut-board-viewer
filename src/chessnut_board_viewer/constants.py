"""Protocol constants shared across the Chessnut HID implementation."""

CHESSNUT_VENDOR_ID = 0x2D80
USAGE_PAGE = 0xFF00

AIR_PRODUCT_FAMILY = 0x8000
PRO_PRODUCT_FAMILY = 0x8100
AIR_PLUS_PRODUCT_FAMILY = 0x8200
EVO_PRODUCT_FAMILY = 0x8300
GO_PRODUCT_FAMILY = 0x8500

SUPPORTED_PRODUCT_FAMILIES = {
    AIR_PRODUCT_FAMILY: "Air",
    PRO_PRODUCT_FAMILY: "Pro",
    AIR_PLUS_PRODUCT_FAMILY: "Air+",
    EVO_PRODUCT_FAMILY: "Evo",
    GO_PRODUCT_FAMILY: "Go",
}

# The EasyLink SDK also lists 0x8400 and 0x8600. Keep them selectable as
# supported Chessnut families even though public model names are unclear.
SDK_KNOWN_PRODUCT_FAMILIES = {
    **SUPPORTED_PRODUCT_FAMILIES,
    0x8400: "Chessnut 0x84xx",
    0x8600: "Chessnut 0x86xx",
}

REALTIME_MODE_COMMAND = bytes([0x21, 0x01, 0x00])
UPLOAD_MODE_COMMAND = bytes([0x21, 0x01, 0x01])
BATTERY_REQUEST_COMMAND = bytes([0x29, 0x01, 0x00])

BOARD_REPORT_ID = 0x01
BATTERY_REPORT_ID = 0x2A
DEFAULT_READ_SIZE = 64
MIN_BOARD_REPORT_LENGTH = 34

# Nibble values from the Chessnut EasyLinkSDK CHESS_PIECES table.
PIECES = ("0", "q", "k", "b", "p", "n", "R", "P", "r", "B", "N", "Q", "K")
