"""Set up a fan found over Bluetooth."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, async_discovered_service_info
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DEFAULT_NAME, DOMAIN
from .device import FanError, FanSmartSyncDevice
from .protocol import SERVICE_UUID


def _is_fan(info: BluetoothServiceInfoBleak) -> bool:
    return SERVICE_UUID in [u.lower() for u in info.service_uuids]


def _label(info: BluetoothServiceInfoBleak) -> str:
    # Every fan advertises the same name ("Fan"), so the address tells them apart.
    return f"{(info.name or 'Fan').strip()} ({info.address})"


class FanSmartSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: BluetoothServiceInfoBleak | None = None
        self._found: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered = discovery_info
        self.context["title_placeholders"] = {"name": _label(discovery_info)}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._discovered is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self._check(self._discovered):
                return self._create(self._discovered, user_input[CONF_NAME])
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({vol.Required(CONF_NAME, default=DEFAULT_NAME): str}),
            description_placeholders={"name": _label(self._discovered)},
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            info = self._found[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(info.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if await self._check(info):
                return self._create(info, user_input[CONF_NAME])
            errors["base"] = "cannot_connect"

        configured = self._async_current_ids(include_ignore=False)
        self._found = {
            info.address: info
            for info in async_discovered_service_info(self.hass, connectable=True)
            if _is_fan(info) and info.address not in configured
        }
        if not self._found:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In({a: _label(i) for a, i in self._found.items()}),
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    async def _check(self, info: BluetoothServiceInfoBleak) -> bool:
        """Read the fan's status once, so setup fails here rather than later."""
        device = FanSmartSyncDevice(info.device)
        try:
            await device.update()
        except FanError:
            return False
        finally:
            await device.disconnect()
        return True

    def _create(self, info: BluetoothServiceInfoBleak, name: str) -> ConfigFlowResult:
        return self.async_create_entry(title=name or DEFAULT_NAME, data={CONF_ADDRESS: info.address})
