from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.hybrid_climate_controller.const import DOMAIN

DATA = {
    "name": "Hybrid",
    "room_sensor": "climate.room",
    "ac_climate": "climate.ac",
    "plugwise_climate": "climate.room",
    "floor_pump": "switch.pump",
    "simulation_mode": False,
    "manage_pump": True,
}


async def setup(hass, **extra):
    hass.states.async_set(
        "climate.room", "heat", {"current_temperature": 18, "temperature_unit": "°C"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data={**DATA, **extra}, version=4)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, hass.data[DOMAIN][entry.entry_id]


@pytest.mark.parametrize("mode", ["dry_run", "virtual"])
async def test_no_physical_calls(hass, mode):
    entry, r = await setup(hass, test_mode=mode)
    with patch.object(type(hass.services), "async_call", new_callable=AsyncMock) as calls:
        r.enabled = True
        r.evaluate()
        r.set_value("room_temperature", 17)
        r.set_value("target_temperature", 24)
        r.set_value("cop", 4)
        hass.states.async_set("climate.room", "heat", {"current_temperature": 17})
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
        await hass.async_block_till_done()
        r.enabled = False
        r.evaluate()
        r.set_mode("dry_run")
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        calls.assert_not_called()
    assert r.closed and not r.unsubs


async def test_virtual_without_devices(hass):
    entry, r = await setup(hass, test_mode="virtual")
    hass.states.async_remove("climate.room")
    r.set_value("room_temperature", 17)
    r.enabled = True
    r.evaluate()
    assert r.decision.source == "hybrid"
    assert r.measured_temperature is None
    assert len(hass.states.async_all(Platform.NUMBER)) == 8
    with pytest.raises(ValueError):
        r.set_mode("live")
    with pytest.raises(ValueError):
        r.set_value("cop", float("nan"))
    for value in range(100):
        r.set_value("target_temperature", 20 + (value % 2))
    assert len(r.history) == 50
    await hass.config_entries.async_unload(entry.entry_id)


async def test_stale_and_unavailable(hass):
    entry, r = await setup(hass)
    r.enabled = True
    r.evaluate()
    assert r.decision.cv_demand
    hass.states.async_set("climate.room", "unavailable", {"current_temperature": 18})
    r.evaluate()
    assert r.decision.source == "unavailable"
    hass.states.async_set(
        "climate.room", "heat", {"current_temperature": 18, "temperature_unit": "°F"}
    )
    assert r.measured_temperature is None
    await hass.config_entries.async_unload(entry.entry_id)


async def test_reload_starts_off(hass):
    entry, r = await setup(hass, test_mode="virtual")
    r.enabled = True
    r.evaluate()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert r.closed
    assert not hass.data[DOMAIN][entry.entry_id].enabled
    await hass.config_entries.async_unload(entry.entry_id)


async def test_entity_services(hass):
    entry, r = await setup(hass, test_mode="virtual")
    physical = AsyncMock()
    for domain, services in {
        "climate": ["set_temperature", "set_hvac_mode"],
        "switch": ["turn_on", "turn_off"],
    }.items():
        # Climate services belong to HA: observe their targets instead of replacing them.
        if domain == "switch":
            for service in services:
                hass.services.async_register(domain, service, physical)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.hybrid_virtual_room_temperature", "value": 17},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.hybrid", "hvac_mode": "heat"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert r.decision.source == "hybrid"
    assert hass.states.get("sensor.hybrid_active_source").state == "hybrid"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.hybrid_simulation_mode", "option": "dry_run"},
        blocking=True,
    )
    assert not r.enabled
    physical.assert_not_called()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_expired_reading(hass, freezer):
    entry, r = await setup(hass)
    r.enabled = True
    freezer.tick(timedelta(minutes=21))
    r.evaluate()
    assert r.decision.source == "unavailable"
    assert r.decision.plugwise_target is None
    # Re-reporting the same reading refreshes last_reported, without a state change.
    hass.states.async_set(
        "climate.room", "heat", {"current_temperature": 18, "temperature_unit": "°C"}
    )
    r.evaluate()
    assert r.decision.source == "hybrid"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_controller_device_and_entity_groups(hass):
    from homeassistant.const import EntityCategory
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.hybrid_climate_controller.const import VERSION

    entry, r = await setup(hass)
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.entry_type == dr.DeviceEntryType.SERVICE
    assert device.model == "Hybrid heating controller (simulation)"
    assert device.sw_version == VERSION
    assert device.name == "Hybrid"
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 31
    assert all(entity.device_id == device.id for entity in entities)
    for entity in entities:
        if entity.domain == "climate":
            assert entity.entity_category is None
        elif entity.domain in ("number", "select"):
            assert entity.entity_category == EntityCategory.CONFIG
        else:
            assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [item.id for item in devices] == [device.id]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_device_with_all_entities_disabled(hass):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    entry, r = await setup(hass)
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        registry.async_update_entity(entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
