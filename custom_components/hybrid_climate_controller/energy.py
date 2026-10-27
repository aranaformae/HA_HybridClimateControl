"""Read Frank-compatible HA tariff states. Never contacts Frank or actuators."""

from datetime import datetime

from homeassistant.util import dt as dt_util

from .engine import finite

PRICE_KEYS = ("electricity_price_entity", "gas_price_entity")


def price_unit(unit, gas=False):
    """Explicit euro units only; no implicit cents/MWh or currency conversions."""
    return unit in (("EUR/m³", "€/m³", "EUR/m3", "€/m3") if gas else ("EUR/kWh", "€/kWh"))


def timestamp(value):
    if isinstance(value, str):
        value = dt_util.parse_datetime(value)
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return dt_util.as_utc(value)


def slots(state, now, gas=False):
    """Normalize documented prices/from/till and analysis slots; retain <=48h."""
    if state is None or state.state in ("unknown", "unavailable"):
        return []
    unit = state.attributes.get("unit_of_measurement")
    if unit is not None and not price_unit(unit, gas):
        return []
    raw = state.attributes.get("prices", state.attributes.get("slots", []))
    if not isinstance(raw, list):
        return []
    result = {}
    for item in raw[:400]:
        if not isinstance(item, dict):
            continue
        start, end = timestamp(item.get("from")), timestamp(item.get("till"))
        price = finite(item.get("price"), 0 if gas else -2, 10 if gas else 5)
        if start is None or end is None or price is None:
            continue
        if not start < end or end <= now or (start - now).total_seconds() > 48 * 3600:
            continue
        if (end - start).total_seconds() > (26 * 3600 if gas else 3600):
            continue
        result[(start, end)] = {"from": start.isoformat(), "till": end.isoformat(), "price": price}
    ordered = sorted(result.values(), key=lambda item: item["from"])
    # Ambiguous overlapping periods must not yield a misleading current price.
    if any(timestamp(a["till"]) > timestamp(b["from"]) for a, b in zip(ordered, ordered[1:])):
        return []
    return ordered


def current_price(state, now, gas=False):
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    if not price_unit(state.attributes.get("unit_of_measurement"), gas):
        return None
    if "prices" in state.attributes or "slots" in state.attributes:
        for slot in slots(state, now, gas):
            if timestamp(slot["from"]) <= now < timestamp(slot["till"]):
                return slot["price"]
        return None  # Never reuse yesterday's or a future slot's tariff.
    reported = getattr(state, "last_reported", state.last_updated)
    age = (now - reported).total_seconds()
    if not 0 <= age <= (26 * 3600 if gas else 2 * 3600):
        return None
    return finite(state.state, 0 if gas else -2, 10 if gas else 5)


def energy_snapshot(hass, cfg, mode, values):
    now = dt_util.utcnow()
    cop = finite(values["cop"] if mode == "virtual" else cfg.get("estimated_cop", 3), 1, 8)
    efficiency = finite(cfg.get("boiler_efficiency", 0.9), 0.5, 1)
    schedule = []
    if mode == "virtual":
        electricity, gas = values["electricity_price"], values["gas_price"]
    else:
        electricity = current_price(hass.states.get(cfg.get(PRICE_KEYS[0], "")), now)
        gas = current_price(hass.states.get(cfg.get(PRICE_KEYS[1], "")), now, True)
        # Current all-in entity already carries today's + tomorrow's prices.
        # Optional extra entities may carry prices or analysis slots.
        entities = [cfg.get(PRICE_KEYS[0]), *cfg.get("future_price_entities", [])]
        combined = {}
        for entity in filter(None, entities):
            for slot in slots(hass.states.get(entity), now):
                combined.setdefault((slot["from"], slot["till"]), slot)
        schedule = sorted(combined.values(), key=lambda item: item["from"])
        if any(timestamp(a["till"]) > timestamp(b["from"]) for a, b in zip(schedule, schedule[1:])):
            schedule = []
    ac_cost = electricity / cop if electricity is not None and cop is not None else None
    cv_cost = gas / (9.77 * efficiency) if gas is not None and efficiency is not None else None
    cheapest = (
        "unknown"
        if ac_cost is None or cv_cost is None
        else "equal"
        if abs(ac_cost - cv_cost) < 0.001
        else "airco"
        if ac_cost < cv_cost
        else "cv"
    )
    return {
        "electricity_price": electricity,
        "gas_price": gas,
        "estimated_cop": cop,
        "boiler_efficiency": efficiency,
        "airco_heat_cost": ac_cost,
        "cv_heat_cost": cv_cost,
        "cheapest_heat_source": cheapest,
        "future_electricity_prices": schedule,
        "tariff_status": "ok"
        if electricity is not None and gas is not None
        else "incomplete_or_invalid",
        "origin": "scenario" if mode == "virtual" else "configured_ha_entities",
        "used_for_control": False,
    }
