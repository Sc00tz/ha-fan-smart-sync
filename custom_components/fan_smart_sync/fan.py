"""The fan motor as a Home Assistant fan entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from .coordinator import FanSmartSyncConfigEntry, FanSmartSyncCoordinator
from .entity import FanSmartSyncEntity

DEFAULT_SPEEDS = 3


async def async_setup_entry(hass: HomeAssistant, entry: FanSmartSyncConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([FanSmartSyncFan(entry.runtime_data)])


class FanSmartSyncFan(FanSmartSyncEntity, FanEntity):
    _attr_name = None  # the device's main feature takes the device name
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    def __init__(self, coordinator: FanSmartSyncCoordinator) -> None:
        super().__init__(coordinator, "fan")
        data = coordinator.data
        self._last_speed = data.speed if data and data.speed else 1

    @property
    def _range(self) -> tuple[int, int]:
        return (1, self.speed_count)

    @property
    def speed_count(self) -> int:
        data = self.coordinator.data
        return data.speed_count if data and data.speed_count else DEFAULT_SPEEDS

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.speed > 0 if self.coordinator.data else None

    @property
    def percentage(self) -> int | None:
        data = self.coordinator.data
        if data is None:
            return None
        if data.speed == 0:
            return 0
        return ranged_value_to_percentage(self._range, min(data.speed, self.speed_count))

    @callback
    def _handle_coordinator_update(self) -> None:
        # Remember the last running speed, so "turn on" goes back to it like the app does.
        data = self.coordinator.data
        if data and data.speed:
            self._last_speed = min(data.speed, self.speed_count)
        super()._handle_coordinator_update()

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        # Nearest speed, so 66% and 67% both mean speed 2 of 3. Any non-zero request runs the fan.
        speed = max(1, min(self.speed_count, round(percentage_to_ranged_value(self._range, percentage))))
        await self.coordinator.run(self.coordinator.device.set_speed(speed))

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self.coordinator.run(self.coordinator.device.set_speed(self._last_speed))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.run(self.coordinator.device.set_speed(0))
