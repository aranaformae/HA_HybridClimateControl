"""Only safe simulation modes are exposed."""

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import SimulationEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SimulationSelect(hass.data[DOMAIN][entry.entry_id])])


class SimulationSelect(SimulationEntity, SelectEntity):
    _attr_options = ["dry_run", "virtual"]

    def __init__(self, runtime):
        super().__init__(runtime, "simulation_mode")

    @property
    def current_option(self):
        return self.runtime.mode

    async def async_select_option(self, option):
        self.runtime.set_mode(option)
