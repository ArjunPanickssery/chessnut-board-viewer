"""Exception types with user-facing diagnostic hints."""


class ChessnutError(Exception):
    """Base class for Chessnut board errors."""

    hint = None

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.hint = hint


class HidUnavailableError(ChessnutError):
    """Raised when Python cannot import the hidapi-backed ``hid`` module."""


class DeviceNotFoundError(ChessnutError):
    """Raised when no matching Chessnut HID interface can be found."""


class DeviceOpenError(ChessnutError):
    """Raised when a HID path is found but cannot be opened."""


class DeviceWriteError(ChessnutError):
    """Raised when a command cannot be written to the HID device."""


class DeviceReadError(ChessnutError):
    """Raised when reading from the HID device fails."""


class ProtocolError(ChessnutError):
    """Raised when a HID report cannot be decoded as Chessnut protocol data."""
