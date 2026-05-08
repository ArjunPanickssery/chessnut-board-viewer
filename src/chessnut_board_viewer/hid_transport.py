"""HID discovery and low-level transport helpers."""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from .constants import (
    CHESSNUT_VENDOR_ID,
    DEFAULT_READ_SIZE,
    PRO_PRODUCT_FAMILY,
    SDK_KNOWN_PRODUCT_FAMILIES,
    USAGE_PAGE,
)
from .errors import (
    DeviceNotFoundError,
    DeviceOpenError,
    DeviceReadError,
    DeviceWriteError,
    HidUnavailableError,
)


def import_hid_module():
    """Import the hidapi-backed Python module with a useful failure message."""

    try:
        return importlib.import_module("hid")
    except Exception as exc:  # pragma: no cover - exercised by CLI diagnostics
        raise HidUnavailableError(
            "Python cannot import the 'hid' module.",
            hint=(
                "Install the hardware extra with: "
                "python3 -m pip install -e '.[hid]'"
            ),
        ) from exc


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    text = str(value)
    return text if text else None


@dataclass(frozen=True)
class HidDeviceInfo:
    """Normalized view of one HID enumeration row."""

    path: Any
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    serial_number: Optional[str] = None
    manufacturer_string: Optional[str] = None
    product_string: Optional[str] = None
    usage_page: Optional[int] = None
    usage: Optional[int] = None
    interface_number: Optional[int] = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "HidDeviceInfo":
        return cls(
            path=data.get("path"),
            vendor_id=_int_or_none(data.get("vendor_id")),
            product_id=_int_or_none(data.get("product_id")),
            serial_number=_clean_string(data.get("serial_number")),
            manufacturer_string=_clean_string(data.get("manufacturer_string")),
            product_string=_clean_string(data.get("product_string")),
            usage_page=_int_or_none(data.get("usage_page")),
            usage=_int_or_none(data.get("usage")),
            interface_number=_int_or_none(data.get("interface_number")),
            raw=dict(data),
        )

    @property
    def path_text(self) -> str:
        return _clean_string(self.path) or "<missing path>"

    @property
    def product_family(self) -> Optional[int]:
        if self.product_id is None:
            return None
        return self.product_id & 0xFF00

    @property
    def model_name(self) -> str:
        family = self.product_family
        if family is None:
            return "Unknown Chessnut"
        return SDK_KNOWN_PRODUCT_FAMILIES.get(family, "Unknown Chessnut")

    @property
    def is_vendor_match(self) -> bool:
        return self.vendor_id == CHESSNUT_VENDOR_ID

    @property
    def is_usage_match(self) -> bool:
        return self.usage_page == USAGE_PAGE

    @property
    def is_known_family(self) -> bool:
        family = self.product_family
        return family in SDK_KNOWN_PRODUCT_FAMILIES if family is not None else False

    def is_candidate(
        self,
        allow_missing_usage_page: bool = True,
        allow_unknown_product: bool = True,
    ) -> bool:
        """Return true if this row looks like the board data HID interface."""

        if not self.is_vendor_match:
            return False
        if self.usage_page is not None and not self.is_usage_match:
            return False
        if self.usage_page is None and not allow_missing_usage_page:
            return False
        if self.product_id is not None and not self.is_known_family and not allow_unknown_product:
            return False
        return self.path is not None

    def warnings(self) -> List[str]:
        warnings = []
        if self.usage_page is None:
            warnings.append("usage_page missing from HID enumeration")
        elif self.usage_page != USAGE_PAGE:
            warnings.append("usage_page is 0x{:04x}, expected 0x{:04x}".format(self.usage_page, USAGE_PAGE))
        if self.product_id is None:
            warnings.append("product_id missing from HID enumeration")
        elif not self.is_known_family:
            warnings.append("product_id 0x{:04x} is not in the EasyLinkSDK family table".format(self.product_id))
        if self.path is None:
            warnings.append("path missing from HID enumeration")
        return warnings

    def summary(self) -> str:
        product = "unknown"
        if self.product_id is not None:
            product = "0x{:04x}".format(self.product_id)
        usage = "missing"
        if self.usage_page is not None:
            usage = "0x{:04x}".format(self.usage_page)
        serial = self.serial_number or "<no serial>"
        label = self.product_string or self.model_name
        return "{} pid={} usage_page={} serial={} path={}".format(
            label,
            product,
            usage,
            serial,
            self.path_text,
        )


def enumerate_hid_devices(
    vendor_id: int = CHESSNUT_VENDOR_ID,
    hid_module: Any = None,
) -> List[HidDeviceInfo]:
    """Return HID devices for a vendor, normalized for cross-platform use."""

    hid = hid_module or import_hid_module()
    try:
        rows = hid.enumerate(vendor_id, 0)
    except TypeError:
        rows = hid.enumerate(vendor_id=vendor_id, product_id=0)
    return [HidDeviceInfo.from_mapping(row) for row in rows]


def find_chessnut_boards(
    hid_module: Any = None,
    preferred_family: int = PRO_PRODUCT_FAMILY,
    allow_missing_usage_page: bool = True,
    allow_unknown_product: bool = True,
) -> List[HidDeviceInfo]:
    """Find likely Chessnut board HID data interfaces, preferring Pro boards."""

    devices = enumerate_hid_devices(CHESSNUT_VENDOR_ID, hid_module=hid_module)
    candidates = [
        device
        for device in devices
        if device.is_candidate(
            allow_missing_usage_page=allow_missing_usage_page,
            allow_unknown_product=allow_unknown_product,
        )
    ]
    candidates.sort(key=lambda device: _candidate_sort_key(device, preferred_family))
    return candidates


def select_chessnut_boards(
    count: int = 1,
    hid_module: Any = None,
    preferred_family: int = PRO_PRODUCT_FAMILY,
) -> List[HidDeviceInfo]:
    boards = find_chessnut_boards(hid_module=hid_module, preferred_family=preferred_family)
    if len(boards) < count:
        raise DeviceNotFoundError(
            "Found {} Chessnut board HID interface(s), need {}.".format(len(boards), count),
            hint=(
                "Run 'chessnut-board diagnose'. On macOS, check that the board is "
                "awake, connected with a data-capable USB cable, and showing the yellow status LED."
            ),
        )
    return boards[:count]


def _candidate_sort_key(device: HidDeviceInfo, preferred_family: int) -> Tuple[int, int, int, str]:
    family = device.product_family
    preferred_rank = 0 if family == preferred_family else 1
    usage_rank = 0 if device.usage_page == USAGE_PAGE else 1
    known_rank = 0 if device.is_known_family else 1
    return (preferred_rank, usage_rank, known_rank, device.path_text)


def command_write_variants(payload: Sequence[int], output_report_size: int = DEFAULT_READ_SIZE) -> List[bytes]:
    """Return conservative HID write variants for platform differences.

    Most Chessnut boards accept the SDK-style payload directly, e.g.
    ``21 01 00`` for realtime mode. Some macOS HID stacks are stricter about
    report size or report-id zero framing, so fallbacks are tried only if the
    direct write fails.
    """

    raw = bytes(payload)
    variants = [raw]
    if len(raw) < output_report_size:
        variants.append(raw + bytes(output_report_size - len(raw)))

    zero_prefixed = bytes([0x00]) + raw
    variants.append(zero_prefixed)
    if len(zero_prefixed) < output_report_size + 1:
        variants.append(zero_prefixed + bytes(output_report_size + 1 - len(zero_prefixed)))

    unique = []
    seen = set()
    for variant in variants:
        if variant not in seen:
            unique.append(variant)
            seen.add(variant)
    return unique


class HidTransport:
    """Thin wrapper around ``hid.device`` with macOS-friendly fallbacks."""

    def __init__(
        self,
        device_info: HidDeviceInfo,
        hid_module: Any = None,
        write_interval_s: float = 0.2,
        output_report_size: int = DEFAULT_READ_SIZE,
        nonblocking: bool = False,
    ):
        self.device_info = device_info
        self.hid_module = hid_module
        self.write_interval_s = write_interval_s
        self.output_report_size = output_report_size
        self.nonblocking = nonblocking
        self.device = None
        self.last_write_time = 0.0
        self.last_write_variant = None

    @property
    def is_open(self) -> bool:
        return self.device is not None

    def open(self) -> None:
        hid = self.hid_module or import_hid_module()
        try:
            device = hid.device()
        except Exception as exc:
            raise DeviceOpenError(
                "Could not create a HID device handle.",
                hint="Verify the hidapi Python package is installed correctly.",
            ) from exc
        try:
            device.open_path(self.device_info.path)
        except Exception as exc:
            raise DeviceOpenError(
                "Could not open Chessnut HID path: {}".format(self.device_info.path_text),
                hint=(
                    "Close other Chessnut/EasyLink apps, unplug/replug the board, "
                    "and confirm macOS sees it in System Information > USB. On macOS, "
                    "also grant Input Monitoring permission to the app running Python "
                    "(Terminal, iTerm, VS Code, or Codex) if prompted. If permission "
                    "is already enabled, remove/reset that Input Monitoring entry, "
                    "restart the app, and let macOS prompt again. If your virtualenv "
                    "uses Apple's Command Line Tools Python, recreate it with "
                    "Homebrew Python or Python.org Python."
                ),
            ) from exc

        try:
            device.set_nonblocking(1 if self.nonblocking else 0)
        except AttributeError:
            pass
        except Exception:
            # set_nonblocking is a convenience only; timeout reads still work on
            # the common hidapi bindings used by this project.
            pass

        self.device = device

    def close(self) -> None:
        if self.device is None:
            return
        try:
            self.device.close()
        finally:
            self.device = None

    def write_command(self, payload: Sequence[int], allow_fallbacks: bool = True) -> int:
        self._require_open()
        variants = command_write_variants(payload, self.output_report_size)
        if not allow_fallbacks:
            variants = variants[:1]

        errors = []
        for variant in variants:
            self._respect_write_interval()
            try:
                result = self._write_once(variant)
            except Exception as exc:
                errors.append("{} bytes: {}".format(len(variant), exc))
                continue
            if int(result or 0) > 0:
                self.last_write_variant = variant
                self.last_write_time = time.monotonic()
                return int(result)
            errors.append("{} bytes: returned {}".format(len(variant), result))

        raise DeviceWriteError(
            "Could not write command {} to Chessnut HID device.".format(bytes(payload).hex(" ")),
            hint="Tried HID write variants: {}".format("; ".join(errors) or "none"),
        )

    def read(self, size: int = DEFAULT_READ_SIZE, timeout_ms: int = 100) -> bytes:
        self._require_open()
        try:
            try:
                data = self.device.read(size, timeout_ms=timeout_ms)
            except TypeError:
                data = self.device.read(size, timeout_ms)
        except Exception as exc:
            raise DeviceReadError(
                "Could not read from Chessnut HID device.",
                hint="The board may have disconnected, gone to sleep, or been opened by another app.",
            ) from exc
        return bytes(data or [])

    def get_serial_number(self) -> Optional[str]:
        if self.device is None:
            return self.device_info.serial_number
        getter = getattr(self.device, "get_serial_number_string", None)
        if getter is None:
            return self.device_info.serial_number
        try:
            return _clean_string(getter()) or self.device_info.serial_number
        except Exception:
            return self.device_info.serial_number

    def _write_once(self, payload: bytes) -> int:
        try:
            return int(self.device.write(list(payload)))
        except TypeError:
            return int(self.device.write(payload))

    def _respect_write_interval(self) -> None:
        if not self.last_write_time or self.write_interval_s <= 0:
            return
        elapsed = time.monotonic() - self.last_write_time
        remaining = self.write_interval_s - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _require_open(self) -> None:
        if self.device is None:
            raise DeviceOpenError(
                "Chessnut HID transport is not open.",
                hint="Call connect() before reading or writing.",
            )
