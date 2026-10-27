"""Downloadable advisory diagnostics; no credentials or raw entry data."""

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = hass.data[DOMAIN][entry.entry_id]
    return {
        "mode": runtime.mode,
        "physical_control_enabled": False,
        "pump_control": "plugwise_external",
        "decision": runtime.decision.attributes(),
        "history": list(runtime.history),
        "virtual_inputs": dict(runtime.values) if runtime.mode == "virtual" else None,
    }
