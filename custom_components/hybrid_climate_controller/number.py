"""Live adjustable virtual scenario inputs; reset safely after reload."""

from homeassistant.components.number import NumberEntity, NumberMode

from .const import DOMAIN
from .entity import SimulationEntity
from .runtime import INPUTS


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VirtualNumber(runtime, key, spec) for key, spec in INPUTS.items()])


class VirtualNumber(SimulationEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime, key, spec):
        super().__init__(runtime, "virtual_" + key)
        self.key = key
        (
            self._attr_native_min_value,
            self._attr_native_max_value,
            self._attr_native_step,
            _,
            self._attr_native_unit_of_measurement,
        ) = spec

    @property
    def native_value(self):
        return self.runtime.values[self.key]

    async def async_set_native_value(self, value):
        self.runtime.set_value(self.key, value)
