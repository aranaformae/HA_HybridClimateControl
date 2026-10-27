"""Measured and advisory diagnostics, never actuator feedback."""

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import SimulationEntity

FIELDS = {
    "active_source": ("source", None),
    "decision_reason": ("reason", None),
    "temperature_deviation": ("deviation", "°C"),
    "heat_demand": ("demand", "%"),
    "desired_daikin_setpoint": ("ac_target", "°C"),
    "desired_plugwise_setpoint": ("plugwise_target", "°C"),
    "simulated_cv_demand": ("cv_demand", None),
}


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DiagnosticSensor(runtime, key)
            for key in [
                *FIELDS,
                "room",
                "decision_log",
                "simulation_mode",
                "temperature_trend",
                "floor_heat",
                "control_status",
            ]
        ]
    )


class DiagnosticSensor(SimulationEntity, SensorEntity):
    def __init__(self, runtime, key):
        super().__init__(runtime, key)
        self.key = key
        self._attr_native_unit_of_measurement = FIELDS.get(key, (None, None))[1]
        if key == "room":
            self._attr_native_unit_of_measurement = "°C"
        elif key == "temperature_trend":
            self._attr_native_unit_of_measurement = "°C/h"
        elif key == "floor_heat":
            self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self):
        r = self.runtime
        if self.key in FIELDS:
            value = getattr(r.decision, FIELDS[self.key][0])
            return ("on" if value else "off") if isinstance(value, bool) else value
        if self.key == "room":
            return r.measured_temperature
        if self.key == "decision_log":
            return len(r.history)
        if self.key == "simulation_mode":
            return r.mode
        if self.key == "control_status":
            return "simulation_only"
        return r.values[self.key] if r.mode == "virtual" else None

    @property
    def extra_state_attributes(self):
        if self.key == "decision_log":
            return {"entries": list(self.runtime.history), "maximum_entries": 50}
        return {
            "physical_control_enabled": False,
            "model_trained": False,
            "origin": "scenario"
            if self.runtime.mode == "virtual" and self.key != "room"
            else "measured"
            if self.key == "room"
            else "advisory",
        }
