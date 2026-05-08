"""High-level Chessnut board client built on the HID transport."""

from __future__ import annotations

import time
from typing import Any, Callable, List, Optional

from .constants import (
    BATTERY_REQUEST_COMMAND,
    DEFAULT_READ_SIZE,
    PRO_PRODUCT_FAMILY,
    REALTIME_MODE_COMMAND,
)
from .errors import ChessnutError, DeviceNotFoundError
from .hid_transport import (
    HidDeviceInfo,
    HidTransport,
    find_chessnut_boards,
)
from .protocol import (
    EMPTY_FEN,
    board_to_ascii,
    decode_battery_report,
    decode_board_report,
    fen_to_board,
    is_board_report,
)


TransportFactory = Callable[[HidDeviceInfo], HidTransport]


class ChessnutBoard:
    """Interface to one Chessnut board over USB HID.

    ``connect()`` returns ``True``/``False`` for compatibility with the
    original scripts. New code that wants a detailed exception should call
    ``connect_or_raise()``.
    """

    def __init__(
        self,
        device_info: Optional[HidDeviceInfo] = None,
        board_index: int = 0,
        hid_module: Any = None,
        transport_factory: Optional[Callable[..., HidTransport]] = None,
        preferred_family: int = PRO_PRODUCT_FAMILY,
    ):
        self.device_info = device_info
        self.board_index = board_index
        self.hid_module = hid_module
        self.transport_factory = transport_factory or HidTransport
        self.preferred_family = preferred_family

        self.transport: Optional[HidTransport] = None
        self.current_fen = EMPTY_FEN
        self.connected = False
        self.last_error: Optional[Exception] = None
        self.last_battery_percent: Optional[int] = None
        self.last_report_at: Optional[float] = None
        self.serial = device_info.serial_number if device_info else None

    @classmethod
    def discover(
        cls,
        hid_module: Any = None,
        preferred_family: int = PRO_PRODUCT_FAMILY,
    ) -> List[HidDeviceInfo]:
        return find_chessnut_boards(
            hid_module=hid_module,
            preferred_family=preferred_family,
        )

    def connect(self) -> bool:
        try:
            self.connect_or_raise()
            return True
        except Exception as exc:
            self.last_error = exc
            self.connected = False
            return False

    def connect_or_raise(self) -> None:
        self.disconnect()
        if self.device_info is None:
            boards = self.discover(
                hid_module=self.hid_module,
                preferred_family=self.preferred_family,
            )
            if self.board_index >= len(boards):
                raise DeviceNotFoundError(
                    "No Chessnut board found for index {}.".format(self.board_index),
                    hint=(
                        "Run 'chessnut-board diagnose'. For a Chessnut Pro, expect "
                        "vendor 0x2d80, product 0x81xx, usage_page 0xff00."
                    ),
                )
            self.device_info = boards[self.board_index]

        transport = self._create_transport(self.device_info)
        try:
            transport.open()
            transport.write_command(REALTIME_MODE_COMMAND)
        except Exception:
            transport.close()
            raise

        self.transport = transport
        self.connected = True
        self.last_error = None
        self.serial = transport.get_serial_number()

    def disconnect(self) -> None:
        self.connected = False
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    def switch_realtime(self) -> bool:
        if not self.transport:
            return False
        self.transport.write_command(REALTIME_MODE_COMMAND)
        return True

    def read_board(self, timeout_ms: int = 5) -> Optional[str]:
        """Read one HID report and return a FEN if it is a board report."""

        if not self.transport:
            return None
        try:
            data = self.transport.read(DEFAULT_READ_SIZE, timeout_ms=timeout_ms)
        except ChessnutError as exc:
            self.last_error = exc
            self.connected = False
            return None

        battery = decode_battery_report(data)
        if battery is not None and battery != 0:
            self.last_battery_percent = battery

        if not data or not is_board_report(data):
            return None

        fen = decode_board_report(data)
        self.current_fen = fen
        self.last_report_at = time.monotonic()
        return fen

    def drain_and_get_latest(self, max_reads: int = 50) -> Optional[str]:
        """Drain queued HID reports and return the newest board FEN."""

        if not self.transport:
            return None
        latest = None
        for _ in range(max_reads):
            try:
                data = self.transport.read(DEFAULT_READ_SIZE, timeout_ms=0)
            except ChessnutError as exc:
                self.last_error = exc
                self.connected = False
                break
            if not data:
                break

            battery = decode_battery_report(data)
            if battery is not None and battery != 0:
                self.last_battery_percent = battery
                continue

            if is_board_report(data):
                latest = decode_board_report(data)
                self.current_fen = latest
                self.last_report_at = time.monotonic()
        return latest

    def get_fen(self) -> str:
        fen = self.read_board()
        if fen:
            self.current_fen = fen
        return self.current_fen

    def get_board_array(self) -> List[List[str]]:
        return fen_to_board(self.current_fen)

    def get_ascii_board(self) -> str:
        return board_to_ascii(self.get_board_array())

    def read_battery(self, timeout_s: float = 1.0) -> Optional[int]:
        """Ask the board for battery status and wait for a battery report."""

        if not self.transport:
            return None
        self.transport.write_command(BATTERY_REQUEST_COMMAND)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            data = self.transport.read(DEFAULT_READ_SIZE, timeout_ms=min(100, remaining_ms))
            battery = decode_battery_report(data)
            if battery is not None and battery != 0:
                self.last_battery_percent = battery
                return battery
            if data and is_board_report(data):
                self.current_fen = decode_board_report(data)
                self.last_report_at = time.monotonic()
        return self.last_battery_percent

    def wait_for_board_report(self, timeout_s: float = 2.0) -> Optional[str]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            fen = self.read_board(timeout_ms=min(100, remaining_ms))
            if fen:
                return fen
        return None

    @property
    def label(self) -> str:
        if self.device_info is None:
            return "Chessnut board"
        serial = self.serial or self.device_info.serial_number
        if serial:
            return "{} {}".format(self.device_info.model_name, serial)
        return self.device_info.product_string or self.device_info.model_name

    def _create_transport(self, device_info: HidDeviceInfo) -> HidTransport:
        try:
            return self.transport_factory(device_info, hid_module=self.hid_module)
        except TypeError:
            return self.transport_factory(device_info)

    def __enter__(self) -> "ChessnutBoard":
        self.connect_or_raise()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()
