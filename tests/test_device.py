"""The Bluetooth layer with a stand-in client: time limits and failure messages."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest
from bleak.backends.device import BLEDevice

from custom_components.fan_smart_sync import device as device_mod
from custom_components.fan_smart_sync import protocol
from custom_components.fan_smart_sync.device import FanError, FanSmartSyncDevice

STATUS = bytes.fromhex("40B01023A3000033000000221B")


class FakeClient:
    """A connected client. `mode` decides how the 'fan' behaves."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.is_connected = True
        self._notify = None

    async def start_notify(self, _uuid, callback) -> None:
        self._notify = callback

    async def write_gatt_char(self, _uuid, data, response: bool) -> None:
        assert response is True
        if self.mode == "write_hangs":
            await asyncio.sleep(3600)
        if self.mode == "ok":
            asyncio.get_running_loop().call_soon(self._notify, None, bytearray(STATUS))
        # "silent": accepts the write but never replies

    async def disconnect(self) -> None:
        self.is_connected = False


def make(mode: str):
    async def connect(*_args, **_kwargs):
        if mode == "connect_hangs":
            await asyncio.sleep(3600)
        return FakeClient(mode)

    return patch.object(device_mod, "establish_connection", side_effect=connect)


@pytest.fixture
def fan():
    return FanSmartSyncDevice(BLEDevice("AA:BB:CC:DD:EE:FF", "Fan", {}))


async def test_reads_status(fan) -> None:
    with make("ok"):
        status = await fan.update()
    assert status.speed_count == 3
    await fan.disconnect()


@pytest.mark.parametrize(("mode", "stage"), [("connect_hangs", "connecting"), ("write_hangs", "reading status")])
async def test_gives_up_within_the_time_limit(fan, mode, stage) -> None:
    with make(mode), patch.object(device_mod, "ATTEMPT_TIMEOUT", 0.2):
        start = time.monotonic()
        with pytest.raises(FanError) as err:
            await fan.update()
    # Two attempts of 0.2 s each, not an hour.
    assert time.monotonic() - start < 2
    assert str(err.value) == f"no answer within 0 s while {stage}"


async def test_no_reply(fan) -> None:
    with make("silent"), patch.object(device_mod, "REPLY_TIMEOUT", 0.05):
        with pytest.raises(FanError) as err:
            await fan.update()
    assert "no reply within 0 s while reading status" in str(err.value)


async def test_command_failure_names_the_stage(fan) -> None:
    with make("silent"), patch.object(device_mod, "REPLY_TIMEOUT", 0.05):
        with pytest.raises(FanError) as err:
            await fan.set_speed(1)
    assert "while sending the command" in str(err.value)
    assert protocol.fan_command(1)  # the frame itself is fine
