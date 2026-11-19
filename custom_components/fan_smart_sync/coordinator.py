"""Polls the fan and shares its status with the entities."""

from __future__ import annotations

import logging
from collections.abc import Awaitable

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
            raise UpdateFailed(f"Couldn't read the fan: {err}") from err

    async def run(self, operation: Awaitable[Status]) -> None:
        """Send a command, then share the status the fan reports afterwards."""
        try:
            status = await operation
        except FanError as err:
            raise HomeAssistantError(f"The fan didn't respond: {err}") from err
        self.async_set_updated_data(status)
