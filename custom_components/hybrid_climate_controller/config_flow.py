"""Configuration and options for simulation-only testing."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_AC, CONF_ASSIST, CONF_BATHROOM, CONF_PLUGWISE, CONF_PUMP, CONF_ROOM, DOMAIN


def schema(defaults):
    climate = selector.EntitySelector(selector.EntitySelectorConfig(domain="climate"))
    return vol.Schema(
        {
            vol.Required("name", default=defaults.get("name", "Hybrid Climate")): str,
            vol.Required(
                CONF_ROOM, default=defaults.get(CONF_ROOM, "climate.woonkamer")
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "climate"])),
            vol.Required(
                CONF_AC, default=defaults.get(CONF_AC, "climate.daikin_woonkamer_room_temperature")
            ): climate,
            vol.Required(
                CONF_PLUGWISE, default=defaults.get(CONF_PLUGWISE, "climate.woonkamer")
            ): climate,
            vol.Optional(
                CONF_PUMP, description={"suggested_value": defaults.get(CONF_PUMP)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
            vol.Optional(
                CONF_BATHROOM, description={"suggested_value": defaults.get(CONF_BATHROOM)}
            ): climate,
            vol.Required("test_mode", default=defaults.get("test_mode", "dry_run")): vol.In(
                ["dry_run", "virtual"]
            ),
            vol.Required(CONF_ASSIST, default=defaults.get(CONF_ASSIST, 1.0)): vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=4)
            ),
        }
    )


def errors(data):
    if data[CONF_AC] == data[CONF_PLUGWISE] or data.get(CONF_BATHROOM) in (
        data[CONF_AC],
        data[CONF_PLUGWISE],
    ):
        return {"base": "overlapping_zones"}
    return {}


class HybridClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 4

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HybridOptionsFlow()

    async def async_step_user(self, user_input=None):
        error = errors(user_input) if user_input else {}
        if user_input is not None and not error:
            await self.async_set_unique_id(user_input[CONF_PLUGWISE])
            self._abort_if_unique_id_configured()
            # Older installations used a composite pump/zone unique id.
            if any(
                entry.data.get(CONF_PLUGWISE) == user_input[CONF_PLUGWISE]
                for entry in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=schema(user_input or {}), errors=error
        )


class HybridOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        error = errors(user_input) if user_input else {}
        if user_input is not None and not error:
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if (
                    entry.entry_id != self.config_entry.entry_id
                    and {**entry.data, **entry.options}.get(CONF_PLUGWISE)
                    == user_input[CONF_PLUGWISE]
                ):
                    error = {"base": "overlapping_zones"}
            if not error:
                return self.async_create_entry(title="", data=user_input)
        defaults = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        return self.async_show_form(step_id="init", data_schema=schema(defaults), errors=error)
