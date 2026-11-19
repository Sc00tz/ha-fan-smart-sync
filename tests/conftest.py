"""Fixtures for the Home Assistant tests. A fake fan stands in for the Bluetooth device."""

from __future__ import annotations

import dataclasses
from unittest.mock import patch

import pytest

from custom_components.fan_smart_sync import protocol

STATUS = protocol.parse_status(protocol.parse(bytes.fromhex("40B01023A3000033000000221B"))[1])


class FakeFan:
    """Behaves like FanSmartSyncDevice, applying commands to an in-memory status."""

    def __init__(self, ble_device) -> None:
        self.address = ble_device.address
        self.status = STATUS
        self.sent: list[tuple] = []
        self.fail = False

    def set_ble_device(self, ble_device) -> None:
        pass

    async def update(self):
        if self.fail:
            from custom_components.fan_smart_sync.device import FanError

            raise FanError("no answer")
        return self.status

    async def set_speed(self, speed: int):
        self.sent.append(("speed", speed))
        self.status = dataclasses.replace(self.status, speed=speed)
        return self.status

    async def set_light(self, on: bool, percent: int):
        self.sent.append(("light", on, percent))
        self.status = dataclasses.replace(self.status, lower_on=on, lower_percent=percent)
        return self.status

    async def disconnect(self) -> None:
        pass


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def fake_fans():
    """Every FanSmartSyncDevice the integration creates, in order."""
    made: list[FakeFan] = []

    def make(ble_device):
        fan = FakeFan(ble_device)
        made.append(fan)
        return fan

    with (
        patch("custom_components.fan_smart_sync.FanSmartSyncDevice", side_effect=make),
        patch("custom_components.fan_smart_sync.config_flow.FanSmartSyncDevice", side_effect=make),
    ):
        yield made
