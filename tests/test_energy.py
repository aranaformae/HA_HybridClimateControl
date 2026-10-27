from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import State
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hybrid_climate_controller.const import DOMAIN
from custom_components.hybrid_climate_controller.energy import current_price, slots


def state(value="0.30", unit="EUR/kWh", **attrs):
    return State("sensor.frank", value, {"unit_of_measurement": unit, **attrs})


def period(now, price, start=0, minutes=15):
    return {
        "from": (now + timedelta(minutes=start)).isoformat(),
        "till": (now + timedelta(minutes=start + minutes)).isoformat(),
        "price": price,
    }


@pytest.mark.parametrize("unit", ["EUR/kWh", "€/kWh"])
def test_current_all_in_and_negative(unit, freezer):
    now = dt_util.utcnow()
    assert current_price(state("-0.1", unit), now) == -0.1
    assert current_price(state("0.9", unit, prices=[period(now, -0.2, -5)]), now) == -0.2


@pytest.mark.parametrize(
    "value,unit",
    [
        ("nan", "EUR/kWh"),
        ("inf", "EUR/kWh"),
        ("unavailable", "EUR/kWh"),
        ("unknown", "EUR/kWh"),
        ("300", "EUR/MWh"),
        ("30", "ct/kWh"),
        ("0.3", "USD/kWh"),
        ("0.3", None),
    ],
)
def test_bad_tariffs(value, unit):
    assert current_price(state(value, unit), dt_util.utcnow()) is None


def test_expired_future_and_overlapping_slots():
    now = dt_util.utcnow()
    assert current_price(state(prices=[period(now, 0.1, -30)]), now) is None
    assert current_price(state(prices=[period(now, 0.1, 15)]), now) is None
    assert slots(state(prices=[period(now, 0.1), period(now, 0.2, 5)]), now) == []
    assert (
        slots(
            state(
                prices=[
                    {"from": "2026-10-27T00:00:00", "till": "2026-10-27T01:00:00", "price": 0.1}
                ]
            ),
            now,
        )
        == []
    )
    assert slots(state(prices="bad"), now) == []
    assert len(slots(state(slots=[period(now, 0.1), {"bad": 1}, period(now, 0.1)]), now)) == 1


def test_gas_and_age(freezer):
    now = dt_util.utcnow()
    gas = state("1.3", "€/m³")
    electricity = state()
    assert current_price(gas, now, True) == 1.3
    assert current_price(state("-1", "€/m³"), now, True) is None
    freezer.tick(timedelta(hours=3))
    assert current_price(electricity, dt_util.utcnow()) is None
    assert current_price(gas, dt_util.utcnow(), True) == 1.3
    freezer.tick(timedelta(hours=24))
    assert current_price(gas, dt_util.utcnow(), True) is None


async def test_tariffs_update_costs_and_no_hardware(hass):
    now = dt_util.utcnow()
    hass.states.async_set(
        "sensor.electricity",
        "0.30",
        {"unit_of_measurement": "€/kWh", "prices": [period(now, 0.30, -5), period(now, 0.10, 10)]},
    )
    hass.states.async_set("sensor.gas", "1.30", {"unit_of_measurement": "€/m³"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data={
            "name": "Hybrid",
            "room_sensor": "sensor.room",
            "ac_climate": "climate.ac",
            "plugwise_climate": "climate.cv",
            "electricity_price_entity": "sensor.electricity",
            "gas_price_entity": "sensor.gas",
            "estimated_cop": 3,
            "boiler_efficiency": 0.9,
        },
    )
    entry.add_to_hass(hass)
    with patch.object(type(hass.services), "async_call", new_callable=AsyncMock) as calls:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        r = hass.data[DOMAIN][entry.entry_id]
        assert r.energy["airco_heat_cost"] == pytest.approx(0.1)
        assert r.energy["cv_heat_cost"] == pytest.approx(1.30 / (9.77 * 0.9))
        assert r.energy["cheapest_heat_source"] == "airco"
        assert len(r.energy["future_electricity_prices"]) == 2
        hass.states.async_set("sensor.electricity", "0.9", {"unit_of_measurement": "€/kWh"})
        await hass.async_block_till_done()
        assert r.energy["cheapest_heat_source"] == "cv"
        assert hass.states.get("sensor.hybrid_airco_heat_cost").state == "0.3"
        hass.states.async_set("sensor.gas", "unavailable", {"unit_of_measurement": "€/m³"})
        await hass.async_block_till_done()
        assert r.energy["cheapest_heat_source"] == "unknown"
        r.set_mode("virtual")
        r.set_value("electricity_price", -0.3)
        assert r.energy["airco_heat_cost"] == pytest.approx(-0.1)
        assert r.energy["origin"] == "scenario"
        assert not r.energy["used_for_control"]
        assert await hass.config_entries.async_unload(entry.entry_id)
        calls.assert_not_called()


@pytest.mark.parametrize("count,minutes", [(24, 60), (96, 15)])
def test_hourly_and_quarter_hour_schedule(count, minutes):
    now = dt_util.utcnow()
    data = [period(now, 0.3, index * minutes, minutes) for index in range(count)]
    assert len(slots(state(prices=data), now)) == count


def test_dst_offsets():
    from custom_components.hybrid_climate_controller.energy import timestamp

    early = timestamp("2026-10-25T02:00:00+02:00")
    late = timestamp("2026-10-25T02:00:00+01:00")
    assert late - early == timedelta(hours=1)
