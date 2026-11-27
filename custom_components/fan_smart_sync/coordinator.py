"""Polls the fan and shares its status with the entities."""

from __future__ import annotations

import logging
from collections.abc import Awaitable

from bluetooth_data_tools import monotonic_time_coarse
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLL_INTERVAL
from .device import FanError, FanSmartSyncDevice
from .protocol import Status

_LOGGER = logging.getLogger(__name__)

type FanSmartSyncConfigEntry = ConfigEntry[FanSmartSyncCoordinator]


class FanSmartSyncCoordinator(DataUpdateCoordinator[Status]):
    config_entry: FanSmartSyncConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FanSmartSyncConfigEntry, device: FanSmartSyncDevice) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {device.address}", update_interval=POLL_INTERVAL)
        self.device = device

    async def _async_update_data(self) -> Status:
        try:
            return await self.device.update()
        except FanError as err:
            message = f"Couldn't read the fan: {err} ({self.radio_context()})"
            if self.data is None:
                # Home Assistant only logs polling failures after setup. Log setup failures too,
                # so a fan that never comes up still leaves a reason in the log.
                _LOGGER.warning("%s: %s. Home Assistant will keep retrying.", self.device.address, message)
            raise UpdateFailed(message) from err

    async def run(self, operation: Awaitable[Status]) -> None:
        """Send a command, then share the status the fan reports afterwards."""
        try:
            status = await operation
        except FanError as err:
            _LOGGER.warning("%s: command failed: %s (%s)", self.device.address, err, self.radio_context())
            raise HomeAssistantError(f"The fan didn't respond: {err}") from err
        self.async_set_updated_data(status)

    def radio_context(self) -> str:
        """Which adapter or proxy last heard the fan, how strongly, and how long ago."""
        try:
            info = bluetooth.async_last_service_info(self.hass, self.device.address, connectable=True)
            if info is None:
                return "Home Assistant hasn't heard the fan advertise recently; it may be out of range or connected to another device, such as a phone running the Fan Smart Sync app"
            scanner = bluetooth.async_scanner_by_source(self.hass, info.source)
            via = f"{scanner.name} ({info.source})" if scanner else info.source
            age = max(0, round(monotonic_time_coarse() - info.time))
            return f"last heard {age} s ago via {via} at {info.rssi} dBm"
        except Exception:  # noqa: BLE001 - context is best effort and must never hide the real error
            return "no Bluetooth details available"
