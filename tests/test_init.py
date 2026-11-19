"""Setup, the config flow and the entities, run inside a real Home Assistant test instance."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.fan_smart_sync.const import DOMAIN, POLL_INTERVAL
from custom_components.fan_smart_sync.protocol import SERVICE_UUID

ADDRESS = "AA:BB:CC:DD:EE:FF"
FAN = "fan.bedroom_fan"
LIGHT = "light.bedroom_fan_light"


def service_info(address: str = ADDRESS) -> BluetoothServiceInfoBleak:
    device = BLEDevice(address, "Fan                 ", {})
    return BluetoothServiceInfoBleak(
        name="Fan                 ", address=address, rssi=-70, manufacturer_data={}, service_data={},
        service_uuids=[SERVICE_UUID], source="local", device=device, advertisement=None,
        connectable=True, time=0, tx_power=None,
    )


@pytest.fixture
def bluetooth_ok():
    """Stand in for the Bluetooth stack: the fan is always visible."""
    info = service_info()
    with (
        patch("custom_components.fan_smart_sync.bluetooth.async_ble_device_from_address", return_value=info.device),
        patch("custom_components.fan_smart_sync.bluetooth.async_register_callback", return_value=lambda: None),
        patch("custom_components.fan_smart_sync.config_flow.async_discovered_service_info", return_value=[info]),
        patch("homeassistant.components.bluetooth_adapters.async_setup", return_value=True, create=True),
    ):
        yield info


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, title="Bedroom fan", data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities(hass: HomeAssistant, bluetooth_ok, fake_fans) -> None:
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    fan = hass.states.get(FAN)
    assert fan.state == STATE_OFF
    assert fan.attributes["percentage_step"] == pytest.approx(100 / 3)

    light = hass.states.get(LIGHT)
    assert light.state == STATE_OFF
    assert light.attributes["supported_color_modes"] == ["brightness"]


async def test_fan_commands(hass: HomeAssistant, bluetooth_ok, fake_fans) -> None:
    await setup_entry(hass)
    fake = fake_fans[0]

    await hass.services.async_call("fan", "set_percentage", {"entity_id": FAN, "percentage": 67}, blocking=True)
    assert fake.sent[-1] == ("speed", 2)
    assert hass.states.get(FAN).state == STATE_ON
    assert hass.states.get(FAN).attributes["percentage"] == 66

    await hass.services.async_call("fan", "set_percentage", {"entity_id": FAN, "percentage": 66}, blocking=True)
    assert fake.sent[-1] == ("speed", 2)
    await hass.services.async_call("fan", "set_percentage", {"entity_id": FAN, "percentage": 33}, blocking=True)
    assert fake.sent[-1] == ("speed", 1)
    await hass.services.async_call("fan", "set_percentage", {"entity_id": FAN, "percentage": 100}, blocking=True)
    assert fake.sent[-1] == ("speed", 3)

    await hass.services.async_call("fan", "turn_off", {"entity_id": FAN}, blocking=True)
    assert fake.sent[-1] == ("speed", 0)
    assert hass.states.get(FAN).state == STATE_OFF

    # Turning on without a speed goes back to the last one, like the app.
    await hass.services.async_call("fan", "turn_on", {"entity_id": FAN}, blocking=True)
    assert fake.sent[-1] == ("speed", 3)

    await hass.services.async_call("fan", "set_percentage", {"entity_id": FAN, "percentage": 10}, blocking=True)
    assert fake.sent[-1] == ("speed", 1)


async def test_light_commands(hass: HomeAssistant, bluetooth_ok, fake_fans) -> None:
    await setup_entry(hass)
    fake = fake_fans[0]

    # Without a brightness, the light comes on at the level the fan remembers (51%).
    await hass.services.async_call("light", "turn_on", {"entity_id": LIGHT}, blocking=True)
    assert fake.sent[-1] == ("light", True, 51)
    assert hass.states.get(LIGHT).state == STATE_ON

    await hass.services.async_call("light", "turn_on", {"entity_id": LIGHT, "brightness_pct": 30}, blocking=True)
    assert fake.sent[-1] == ("light", True, 30)
    assert hass.states.get(LIGHT).attributes["brightness"] == 76

    # Off keeps the level.
    await hass.services.async_call("light", "turn_off", {"entity_id": LIGHT}, blocking=True)
    assert fake.sent[-1] == ("light", False, 30)
    assert hass.states.get(LIGHT).state == STATE_OFF


async def test_unavailable_when_fan_stops_answering(hass: HomeAssistant, bluetooth_ok, fake_fans) -> None:
    await setup_entry(hass)
    fake_fans[0].fail = True
    from homeassistant.util import dt as dt_util

    async_fire_time_changed(hass, dt_util.utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == STATE_UNAVAILABLE

    fake_fans[0].fail = False
    async_fire_time_changed(hass, dt_util.utcnow() + POLL_INTERVAL * 2)
    await hass.async_block_till_done()
    assert hass.states.get(FAN).state == STATE_OFF


async def test_bluetooth_discovery_flow(hass: HomeAssistant, bluetooth_ok, fake_fans) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=bluetooth_ok)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_NAME: "Bedroom fan"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom fan"
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_user_flow_and_duplicate(hass: HomeAssistant, bluetooth_ok, fake_fans) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ADDRESS: ADDRESS, CONF_NAME: "Bedroom fan"})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=bluetooth_ok)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_cannot_connect(hass: HomeAssistant, bluetooth_ok, fake_fans) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=bluetooth_ok)
    with patch("custom_components.fan_smart_sync.config_flow.FanSmartSyncDevice") as dev:
        from custom_components.fan_smart_sync.device import FanError

        dev.return_value.update = AsyncMock(side_effect=FanError("busy"))
        dev.return_value.disconnect = AsyncMock()
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_NAME: "Bedroom fan"})
    assert result["errors"] == {"base": "cannot_connect"}
