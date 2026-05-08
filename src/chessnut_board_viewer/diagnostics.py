"""User-facing diagnostics for Chessnut USB HID setup."""

from __future__ import annotations

import platform
import sys
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .board import ChessnutBoard
from .constants import CHESSNUT_VENDOR_ID, PRO_PRODUCT_FAMILY, USAGE_PAGE
from .errors import ChessnutError, HidUnavailableError
from .hid_transport import (
    HidDeviceInfo,
    enumerate_hid_devices,
    find_chessnut_boards,
    import_hid_module,
)


@dataclass
class DiagnosticReport:
    platform_text: str
    python_text: str
    python_executable: str
    python_realpath: str
    python_base_prefix: str
    hid_available: bool
    hid_module_file: Optional[str] = None
    hid_error: Optional[str] = None
    hid_hint: Optional[str] = None
    devices: List[HidDeviceInfo] = field(default_factory=list)
    candidates: List[HidDeviceInfo] = field(default_factory=list)
    enumeration_error: Optional[str] = None


@dataclass
class SmokeResult:
    index: int
    device: Optional[HidDeviceInfo]
    connected: bool = False
    fen: Optional[str] = None
    battery_percent: Optional[int] = None
    error: Optional[str] = None
    hint: Optional[str] = None


def collect_diagnostics(hid_module: Any = None) -> DiagnosticReport:
    report = DiagnosticReport(
        platform_text=platform.platform(),
        python_text=sys.version.split()[0],
        python_executable=sys.executable,
        python_realpath=os.path.realpath(sys.executable),
        python_base_prefix=sys.base_prefix,
        hid_available=False,
    )

    try:
        hid = hid_module or import_hid_module()
    except HidUnavailableError as exc:
        report.hid_error = str(exc)
        report.hid_hint = exc.hint
        return report

    report.hid_available = True
    report.hid_module_file = getattr(hid, "__file__", None)
    try:
        report.devices = enumerate_hid_devices(CHESSNUT_VENDOR_ID, hid_module=hid)
        report.candidates = find_chessnut_boards(hid_module=hid)
    except Exception as exc:
        report.enumeration_error = "{}: {}".format(type(exc).__name__, exc)

    return report


def format_diagnostics(report: DiagnosticReport) -> str:
    lines = [
        "Chessnut USB HID diagnostics",
        "Platform: {}".format(report.platform_text),
        "Python: {}".format(report.python_text),
        "Python executable: {}".format(report.python_executable),
        "Python realpath: {}".format(report.python_realpath),
    ]
    python_warning = _macos_python_warning(report)
    if python_warning:
        lines.append("Python warning: {}".format(python_warning))

    if not report.hid_available:
        lines.append("hid module: NOT AVAILABLE")
        if report.hid_error:
            lines.append("  {}".format(report.hid_error))
        if report.hid_hint:
            lines.append("  Hint: {}".format(report.hid_hint))
        return "\n".join(lines + _general_macos_hints())

    lines.append("hid module: OK{}".format(" ({})".format(report.hid_module_file) if report.hid_module_file else ""))

    if report.enumeration_error:
        lines.append("Enumeration error: {}".format(report.enumeration_error))
        return "\n".join(lines + _general_macos_hints())

    lines.append(
        "Expected board interface: vendor=0x{:04x}, Pro product family=0x{:04x}, usage_page=0x{:04x}".format(
            CHESSNUT_VENDOR_ID,
            PRO_PRODUCT_FAMILY,
            USAGE_PAGE,
        )
    )
    lines.append("Chessnut vendor HID rows: {}".format(len(report.devices)))
    for index, device in enumerate(report.devices):
        marker = "candidate" if device in report.candidates else "ignored"
        lines.append("  [{}] {}: {}".format(index, marker, device.summary()))
        for warning in device.warnings():
            lines.append("       warning: {}".format(warning))

    if report.candidates:
        lines.append("Usable board interfaces: {}".format(len(report.candidates)))
        for index, device in enumerate(report.candidates):
            lines.append("  Board {}: {}".format(index, device.summary()))
        if _has_keyboard_collection(report.devices):
            lines.append(
                "macOS note: this board also exposes a keyboard-like HID collection; "
                "opening it may require Input Monitoring permission for the app running Python."
            )
        lines.append("Next: run 'chessnut-board smoke --boards 1' or 'chessnut-board watch'.")
    else:
        lines.append("Usable board interfaces: 0")
        lines.extend(_general_macos_hints())

    return "\n".join(lines)


def smoke_test_boards(
    board_count: int = 1,
    timeout_s: float = 3.0,
    hid_module: Any = None,
) -> List[SmokeResult]:
    """Connect to one or more boards and wait for realtime reports."""

    try:
        devices = find_chessnut_boards(hid_module=hid_module)
    except ChessnutError as exc:
        return [
            SmokeResult(
                index=0,
                device=None,
                error=str(exc),
                hint=exc.hint,
            )
        ]

    results = []
    selected = devices[:board_count]
    if len(selected) < board_count:
        results.append(
            SmokeResult(
                index=len(selected),
                device=None,
                error="Found {} board interface(s), need {}.".format(len(selected), board_count),
                hint="Run diagnostics and verify both boards are awake and connected by USB.",
            )
        )

    boards = []
    try:
        for index, device in enumerate(selected):
            board = ChessnutBoard(device_info=device, hid_module=hid_module)
            try:
                board.connect_or_raise()
            except ChessnutError as exc:
                results.append(
                    SmokeResult(
                        index=index,
                        device=device,
                        connected=False,
                        error=str(exc),
                        hint=exc.hint,
                    )
                )
                continue
            boards.append((index, board))
            results.append(SmokeResult(index=index, device=device, connected=True))

        for index, board in boards:
            fen = board.wait_for_board_report(timeout_s=timeout_s)
            battery = board.last_battery_percent
            for result in results:
                if result.index == index and result.device == board.device_info:
                    result.fen = fen
                    result.battery_percent = battery
                    if not fen:
                        result.error = "Connected, but no realtime board report arrived within {:.1f}s.".format(timeout_s)
                        result.hint = (
                            "Confirm the board is in yellow LED USB mode, move a piece, "
                            "and close any other application using the board."
                        )
                    break
    finally:
        for _, board in boards:
            board.disconnect()

    return results


def format_smoke_results(results: List[SmokeResult]) -> str:
    lines = ["Chessnut hardware smoke test"]
    for result in results:
        label = "Board {}".format(result.index)
        if result.device is not None:
            label += " ({})".format(result.device.summary())
        if result.connected and result.fen:
            lines.append("{}: OK".format(label))
            lines.append("  FEN: {}".format(result.fen))
            if result.battery_percent is not None:
                lines.append("  Battery: {}%".format(result.battery_percent))
        elif result.connected:
            lines.append("{}: CONNECTED, NO BOARD REPORT".format(label))
            if result.error:
                lines.append("  {}".format(result.error))
            if result.hint:
                lines.append("  Hint: {}".format(result.hint))
        else:
            lines.append("{}: FAILED".format(label))
            if result.error:
                lines.append("  {}".format(result.error))
            if result.hint:
                lines.append("  Hint: {}".format(result.hint))
    return "\n".join(lines)


def _general_macos_hints() -> List[str]:
    return [
        "macOS checks:",
        "  - Use a data-capable USB cable, not a charge-only cable.",
        "  - Wake the board and put it in yellow status LED USB/EasyLink mode.",
        "  - Use a Homebrew or Python.org Python virtualenv; Apple's Command Line Tools Python can be denied by TCC as a platform binary.",
        "  - If macOS asks for Input Monitoring, grant it to the app running Python and restart that app.",
        "  - Close Chessnut apps, browser tabs, or old viewers that may hold the HID device.",
        "  - Check Apple menu > About This Mac > More Info > System Report > USB for vendor 0x2d80.",
        "  - Unplug/replug the board after changing mode.",
    ]


def _has_keyboard_collection(devices: List[HidDeviceInfo]) -> bool:
    return any(device.usage_page == 0x0001 and device.usage == 0x0006 for device in devices)


def _macos_python_warning(report: DiagnosticReport) -> Optional[str]:
    if platform.system() != "Darwin":
        return None
    paths = (report.python_realpath, report.python_base_prefix)
    if any(path.startswith("/Library/Developer/CommandLineTools/") for path in paths):
        return (
            "this virtualenv uses Apple's Command Line Tools Python; for HID "
            "keyboard-like devices, recreate it with Homebrew Python or Python.org Python."
        )
    if any(path.startswith("/usr/bin/") or path.startswith("/System/") for path in paths):
        return (
            "this virtualenv appears to use an Apple platform Python; recreate it "
            "with Homebrew Python or Python.org Python for HID access."
        )
    return None
