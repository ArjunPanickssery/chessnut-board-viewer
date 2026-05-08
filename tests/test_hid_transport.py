import pytest

from chessnut_board_viewer.constants import REALTIME_MODE_COMMAND, USAGE_PAGE
from chessnut_board_viewer.errors import DeviceOpenError
from chessnut_board_viewer.hid_transport import (
    HidTransport,
    command_write_variants,
    find_chessnut_boards,
)

from .fakes import FakeHidDevice, FakeHidModule, device_row


def test_find_chessnut_boards_prefers_pro_usage_page_interface():
    rows = [
        device_row(path=b"air", product_id=0x8002, serial_number="AIR"),
        device_row(path=b"wrong-usage", product_id=0x8100, usage_page=0x0001, serial_number="BAD"),
        device_row(path=b"pro", product_id=0x8102, serial_number="PRO"),
    ]
    boards = find_chessnut_boards(hid_module=FakeHidModule(rows=rows))

    assert [board.path for board in boards] == [b"pro", b"air"]
    assert boards[0].model_name == "Pro"


def test_find_chessnut_boards_allows_missing_usage_page_on_incomplete_platforms():
    row = device_row(path=b"missing-usage", usage_page=None)
    boards = find_chessnut_boards(hid_module=FakeHidModule(rows=[row]))

    assert len(boards) == 1
    assert "usage_page missing" in boards[0].warnings()[0]


def test_command_write_variants_are_ordered_from_sdk_payload_to_fallbacks():
    variants = command_write_variants(REALTIME_MODE_COMMAND)

    assert variants[0] == REALTIME_MODE_COMMAND
    assert len(variants[1]) == 64
    assert variants[2].startswith(b"\x00" + REALTIME_MODE_COMMAND)
    assert len(variants[3]) == 65


def test_transport_opens_path_sets_blocking_and_writes_direct_payload():
    fake_device = FakeHidDevice()
    info = find_chessnut_boards(
        hid_module=FakeHidModule(rows=[device_row(path=b"board")], devices=[fake_device])
    )[0]
    hid = FakeHidModule(rows=[device_row(path=b"board")], devices=[fake_device])
    transport = HidTransport(info, hid_module=hid, write_interval_s=0)

    transport.open()
    written = transport.write_command(REALTIME_MODE_COMMAND)

    assert fake_device.opened_path == b"board"
    assert fake_device.nonblocking == 0
    assert fake_device.writes == [REALTIME_MODE_COMMAND]
    assert written == 3


def test_transport_falls_back_to_padded_write_when_direct_write_fails():
    fake_device = FakeHidDevice(write_results=[OSError("bad report"), 64])
    info = find_chessnut_boards(hid_module=FakeHidModule(rows=[device_row(path=b"board")]))[0]
    transport = HidTransport(info, hid_module=FakeHidModule(devices=[fake_device]), write_interval_s=0)

    transport.open()
    written = transport.write_command(REALTIME_MODE_COMMAND)

    assert written == 64
    assert fake_device.writes[0] == REALTIME_MODE_COMMAND
    assert len(fake_device.writes[1]) == 64


def test_transport_open_failure_has_hint():
    info = find_chessnut_boards(hid_module=FakeHidModule(rows=[device_row(path=b"open-fails")]))[0]
    transport = HidTransport(info, hid_module=FakeHidModule(devices=[FakeHidDevice()]))

    with pytest.raises(DeviceOpenError) as excinfo:
        transport.open()

    assert "Close other Chessnut" in excinfo.value.hint
    assert "Input Monitoring" in excinfo.value.hint
    assert "remove/reset" in excinfo.value.hint
