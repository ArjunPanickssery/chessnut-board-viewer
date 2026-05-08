from chessnut_board_viewer import cli
from chessnut_board_viewer.diagnostics import DiagnosticReport, SmokeResult
from chessnut_board_viewer.hid_transport import HidDeviceInfo

from .fakes import device_row


def test_cli_defaults_to_diagnose(monkeypatch, capsys):
    report = DiagnosticReport(
        platform_text="test-os",
        python_text="3.x",
        python_executable="/tmp/python",
        python_realpath="/tmp/python",
        python_base_prefix="/tmp",
        hid_available=True,
    )
    monkeypatch.setattr(cli, "collect_diagnostics", lambda: report)

    assert cli.main([]) == 0

    assert "Chessnut USB HID diagnostics" in capsys.readouterr().out


def test_cli_list_prints_candidate(monkeypatch, capsys):
    device = HidDeviceInfo.from_mapping(device_row(path=b"board"))
    report = DiagnosticReport(
        platform_text="test-os",
        python_text="3.x",
        python_executable="/tmp/python",
        python_realpath="/tmp/python",
        python_base_prefix="/tmp",
        hid_available=True,
        devices=[device],
        candidates=[device],
    )
    monkeypatch.setattr(cli, "collect_diagnostics", lambda: report)

    assert cli.main(["list"]) == 0

    assert "Chessnut Pro" in capsys.readouterr().out


def test_cli_smoke_failure_sets_nonzero_exit(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "smoke_test_boards",
        lambda board_count, timeout_s: [
            SmokeResult(
                index=0,
                device=None,
                connected=False,
                error="Found 0 board interface(s), need 1.",
            )
        ],
    )

    assert cli.main(["smoke"]) == 1

    assert "FAILED" in capsys.readouterr().out
