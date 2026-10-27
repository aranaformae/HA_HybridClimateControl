import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import *

class HybridClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 4
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PLUGWISE] + "_" + user_input[CONF_PUMP])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_NAME, default="Hybride woonkamer"): str,
            vol.Required(CONF_ROOM): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "climate"])),
            vol.Required(CONF_AC, default="climate.daikin_woonkamer_room_temperature"): selector.EntitySelector(selector.EntitySelectorConfig(domain="climate")),
            vol.Required(CONF_PLUGWISE, default="climate.woonkamer"): selector.EntitySelector(selector.EntitySelectorConfig(domain="climate")),
            vol.Required(CONF_PUMP, default="switch.vloerverwarmingspomp"): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
            vol.Optional(CONF_PUMP_MANAGED, default=False): bool,
            vol.Optional(CONF_SIMULATION, default=True): bool,
            vol.Optional(CONF_SIM_TEMP): vol.All(vol.Coerce(float), vol.Range(min=5, max=35)),
            vol.Optional(CONF_BATHROOM, default="climate.badkamer"): selector.EntitySelector(selector.EntitySelectorConfig(domain="climate")),
            vol.Optional(CONF_ASSIST, default=DEFAULT_ASSIST): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=4)),
            vol.Optional(CONF_MIN_ON, default=DEFAULT_MIN_ON): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
            vol.Optional(CONF_MIN_OFF, default=DEFAULT_MIN_OFF): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
            vol.Optional(CONF_POSTRUN, default=DEFAULT_POSTRUN): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
        })
        return self.async_show_form(step_id="user", data_schema=schema)
