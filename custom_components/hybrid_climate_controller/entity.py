"""Common entry device and dispatcher subscription."""

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CONF_NAME, DOMAIN


class SimulationEntity(Entity):
    _attr_should_poll = False

    def __init__(self, runtime, key):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_name = f"{runtime.cfg.get(CONF_NAME, 'Hybrid')} {key.replace('_', ' ')}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            name=runtime.cfg.get(CONF_NAME, "Hybrid"),
            manufacturer="HA Hybrid Climate Control",
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.runtime.signal, self.async_write_ha_state)
        )
