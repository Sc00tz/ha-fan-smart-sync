"""Fan Smart Sync ceiling fans over Bluetooth."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import FanSmartSyncConfigEntry, FanSmartSyncCoordinator
from .device import FanSmartSyncDevice

PLATFORMS = [Platform.FAN, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: FanSmartSyncConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(f"Couldn't find the fan {address}. Is it powered and in Bluetooth range?")

    device = FanSmartSyncDevice(ble_device)
    coordinator = FanSmartSyncCoordinator(hass, entry, device)

    @callback
    def _seen(service_info: bluetooth.BluetoothServiceInfoBleak, _change: bluetooth.BluetoothChange) -> None:
        device.set_ble_device(service_info.device)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass, _seen, bluetooth.BluetoothCallbackMatcher(address=address, connectable=True), bluetooth.BluetoothScanningMode.PASSIVE
        )
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FanSmartSyncConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.device.disconnect()
    return unloaded
