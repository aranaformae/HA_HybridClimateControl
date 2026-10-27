"""Common entry device and dispatcher subscription."""

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CONF_NAME, DOMAIN, VERSION


class SimulationEntity(Entity):
    _attr_should_poll = False

    def __init__(self, runtime, key):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_name = f"{runtime.cfg.get(CONF_NAME, 'Hybrid')} {key.replace('_', ' ')}"
        self._attr_device_info = controller_device_info(runtime.entry.entry_id, runtime.cfg)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.runtime.signal, self.async_write_ha_state)
        )


def controller_device_info(entry_id, cfg):
    """One logical service device per controller; retain existing identifiers."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=cfg.get(CONF_NAME, "Hybrid Climate Controller"),
        manufacturer="HA Hybrid Climate Control",
        model="Hybrid heating controller (simulation)",
        sw_version=VERSION,
        entry_type=DeviceEntryType.SERVICE,
    )
