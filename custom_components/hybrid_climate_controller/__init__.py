"""Safe simulation entry lifecycle."""

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .entity import controller_device_info
from .runtime import SimulationRuntime

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.NUMBER, Platform.SELECT]


async def async_setup_entry(hass, entry):
    runtime = SimulationRuntime(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    # Register independently of enabled entities, so a configured controller always
    # has a visible device page, including when all its entities are disabled.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **controller_device_info(entry.entry_id, runtime.cfg),
    )
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        runtime.close()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    runtime.start()
    runtime.evaluate()
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id).close()
    return True
