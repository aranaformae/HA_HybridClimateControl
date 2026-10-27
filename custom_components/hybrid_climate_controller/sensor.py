from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback
from .const import CONF_ROOM, CONF_NAME

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HybridRoomSensor(hass, entry)])

class HybridRoomSensor(SensorEntity):
    _attr_icon = "mdi:thermometer"
    _attr_should_poll = False
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = entry.entry_id + "_room"
        self._attr_name = entry.data[CONF_NAME] + " gemeten temperatuur"
        self._unsub = None
    @property
    def native_value(self):
        s = self.hass.states.get(self.entry.data[CONF_ROOM])
        try:
            return float(s.state) if s else None
        except (ValueError, TypeError):
            return None
    @property
    def native_unit_of_measurement(self):
        return "°C"
    async def async_added_to_hass(self):
        self._unsub = async_track_state_change_event(self.hass, [self.entry.data[CONF_ROOM]], self._changed)
    @callback
    def _changed(self, event):
        self.async_write_ha_state()
    async def async_will_remove_from_hass(self):
        if self._unsub:
            self._unsub()
