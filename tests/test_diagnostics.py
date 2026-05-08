from chessnut_board_viewer.diagnostics import (
    collect_diagnostics,
    format_diagnostics,
    format_smoke_results,
    smoke_test_boards,
)

from .fakes import FakeHidDevice, FakeHidModule, device_row, encode_board_report


def test_diagnostics_reports_candidates_and_expected_ids():
    keyboard_row = device_row(path=b"board", usage_page=0x0001)
    keyboard_row["usage"] = 0x0006
    report = collect_diagnostics(
        hid_module=FakeHidModule(rows=[keyboard_row, device_row(path=b"board")])
    )
    text = format_diagnostics(report)

    assert report.hid_available
    assert len(report.candidates) == 1
    assert "vendor=0x2d80" in text
    assert "usage_page=0xff00" in text
    assert "Input Monitoring" in text
    assert "Usable board interfaces: 1" in text


def test_diagnostics_reports_no_device_hints():
    text = format_diagnostics(collect_diagnostics(hid_module=FakeHidModule(rows=[])))

    assert "Usable board interfaces: 0" in text
    assert "Use a data-capable USB cable" in text


def test_diagnostics_warns_for_apple_command_line_tools_python():
    report = collect_diagnostics(hid_module=FakeHidModule(rows=[]))
    report.python_realpath = "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9"
    report.python_base_prefix = "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9"

    text = format_diagnostics(report)

    assert "Python warning" in text
    assert "Homebrew Python" in text


def test_smoke_test_connects_and_reports_fen():
    fen = "8/8/8/8/8/2B5/8/8"
    hid = FakeHidModule(
        rows=[device_row(path=b"board")],
        devices=[FakeHidDevice(reads=[encode_board_report(fen)])],
    )

    results = smoke_test_boards(board_count=1, timeout_s=0.1, hid_module=hid)
    text = format_smoke_results(results)

    assert results[0].connected
    assert results[0].fen == fen
    assert "OK" in text


def test_smoke_test_reports_missing_second_board():
    hid = FakeHidModule(rows=[device_row(path=b"board")], devices=[FakeHidDevice()])

    results = smoke_test_boards(board_count=2, timeout_s=0.01, hid_module=hid)

    assert any(result.error and "need 2" in result.error for result in results)
