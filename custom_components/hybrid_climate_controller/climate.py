"""Advisory thermostat. Never sends commands to physical equipment."""

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .engine import finite
from .entity import SimulationEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HybridClimate(hass.data[DOMAIN][entry.entry_id])])


class HybridClimate(SimulationEntity, ClimateEntity, RestoreEntity):
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 16
    _attr_max_temp = 25

    def __init__(self, runtime):
        super().__init__(runtime, "climate")
        # Preserve existing thermostat entity registry identity.
        self._attr_unique_id = runtime.entry.entry_id
        self._attr_name = runtime.cfg.get("name", "Hybrid")

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if previous:
            target = finite(previous.attributes.get(ATTR_TEMPERATURE), 16, 25)
            if target is not None:
                self.runtime.target = target
                self.runtime.values["target_temperature"] = target
        # Never restore enabled state.

    @property
    def hvac_mode(self):
        return HVACMode.HEAT if self.runtime.enabled else HVACMode.OFF

    @property
    def hvac_action(self):
        if not self.runtime.enabled:
            return HVACAction.OFF
        return (
            HVACAction.HEATING
            if self.runtime.decision.source in ("airco", "floor", "hybrid")
            else HVACAction.IDLE
        )

    @property
    def current_temperature(self):
        return self.runtime.room

    @property
    def target_temperature(self):
        return (
            self.runtime.values["target_temperature"]
            if self.runtime.mode == "virtual"
            else self.runtime.target
        )

    @property
    def extra_state_attributes(self):
        return {
            "simulation_mode": self.runtime.mode,
            "physical_control_enabled": False,
            "pump_control": "plugwise_external",
            "decision": self.runtime.decision.attributes(),
        }

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode not in self.hvac_modes:
            raise ValueError("Unsupported HVAC mode")
        self.runtime.enabled = hvac_mode == HVACMode.HEAT
        self.runtime.evaluate()

    async def async_set_temperature(self, **kwargs):
        value = finite(kwargs.get(ATTR_TEMPERATURE), 16, 25)
        if value is None:
            raise ValueError("Target outside range")
        self.runtime.target = value
        self.runtime.values["target_temperature"] = value
        self.runtime.evaluate()

    async def async_turn_on(self):
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self):
        await self.async_set_hvac_mode(HVACMode.OFF)
