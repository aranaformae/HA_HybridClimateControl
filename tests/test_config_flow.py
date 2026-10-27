from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hybrid_climate_controller.const import DOMAIN

DATA = {
    "name": "Hybrid",
    "room_sensor": "climate.room",
    "ac_climate": "climate.ac",
    "plugwise_climate": "climate.room",
    "test_mode": "virtual",
    "assist_delta": 1.0,
}


async def test_config_and_duplicate(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    again = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=DATA
    )
    assert again["type"] == FlowResultType.ABORT
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_options_and_overlap(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, version=4)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**DATA, "ac_climate": "climate.room"}
    )
    assert result["errors"] == {"base": "overlapping_zones"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            **DATA,
            "assist_delta": 2.0,
            "electricity_price_entity": "sensor.frank",
            "gas_price_entity": "sensor.frank_gas",
            "estimated_cop": 4.0,
            "boiler_efficiency": 0.85,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["assist_delta"] == 2.0

    assert entry.options["electricity_price_entity"] == "sensor.frank"
    assert entry.options["estimated_cop"] == 4.0
