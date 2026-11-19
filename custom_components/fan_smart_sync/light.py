"""The fan's light as a Home Assistant light entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FanSmartSyncConfigEntry, FanSmartSyncCoordinator
from .entity import FanSmartSyncEntity


async def async_setup_entry(hass: HomeAssistant, entry: FanSmartSyncConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    # Only fans that report a light get one. The first status read happens before platforms load.
    if coordinator.data is None or coordinator.data.lower_light:
        async_add_entities([FanSmartSyncLight(coordinator)])


def to_percent(brightness: int) -> int:
    return max(1, min(100, round(brightness * 100 / 255)))


def to_brightness(percent: int) -> int:
    return max(1, min(255, round(percent * 255 / 100)))


class FanSmartSyncLight(FanSmartSyncEntity, LightEntity):
    _attr_translation_key = "light"

    def __init__(self, coordinator: FanSmartSyncCoordinator) -> None:
        super().__init__(coordinator, "light")
        data = coordinator.data
        mode = ColorMode.BRIGHTNESS if data is None or data.lower_dimmable else ColorMode.ONOFF
        self._attr_supported_color_modes = {mode}
        self._attr_color_mode = mode

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.lower_on if self.coordinator.data else None

    @property
    def brightness(self) -> int | None:
        data = self.coordinator.data
        if data is None or self._attr_color_mode != ColorMode.BRIGHTNESS:
            return None
        return to_brightness(data.lower_percent or 100)

    def _kept_percent(self) -> int:
        """The level the fan remembers, used when turning on without a brightness."""
        data = self.coordinator.data
        return data.lower_percent if data and data.lower_percent else 100

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs and self._attr_color_mode == ColorMode.BRIGHTNESS:
            percent = to_percent(kwargs[ATTR_BRIGHTNESS])
        elif self._attr_color_mode == ColorMode.BRIGHTNESS:
            percent = self._kept_percent()
        else:
            percent = 100
        await self.coordinator.run(self.coordinator.device.set_light(True, percent))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.run(self.coordinator.device.set_light(False, self._kept_percent()))
