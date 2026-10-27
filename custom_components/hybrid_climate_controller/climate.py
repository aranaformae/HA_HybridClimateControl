"""Hybrid air-to-air / Plugwise floor heat demand controller.

EXPERIMENTAL. Pump control requires verified hydraulic fail-safe. Does not touch
bathroom climate or boiler directly. Setpoint-based Plugwise heat demand is not
proof that the boiler is running. Do not use without independent pump safety.
"""
import logging
from datetime import timedelta
from time import monotonic
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from .const import *
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HybridClimate(hass, entry)])

class HybridClimate(ClimateEntity, RestoreEntity):
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 16
    _attr_max_temp = 25
    _attr_should_poll = False

    def __init__(self, hass, entry):
        self.hass, self.entry, self.cfg = hass, entry, entry.data
        self._attr_unique_id = entry.entry_id
        self._attr_name = self.cfg[CONF_NAME]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 20.0
        self._attr_hvac_action = HVACAction.OFF
        self._last_pump_change = monotonic() - 7200
        self._last_ac_change = monotonic() - 7200
        self._last_plugwise_change = monotonic() - 7200
        self._pump_demand_ended = None
        self._floor_requested = False
        self._source = "off"
        self._busy = False
        self._unsubs = []
        self._error = None
        self._simulated_commands = []

    @property
    def current_temperature(self):
        if self.cfg.get(CONF_SIM_TEMP) is not None and self.cfg.get(CONF_SIMULATION, True):
            return float(self.cfg[CONF_SIM_TEMP])
        state = self.hass.states.get(self.cfg[CONF_ROOM])
        try:
            raw = state.attributes.get("current_temperature") if state and state.domain == "climate" else (state.state if state else None)
            value = float(raw)
            return value if -20 <= value <= 60 else None
        except (ValueError, TypeError, AttributeError):
            return None

    @property
    def extra_state_attributes(self):
        return {"active_source": self._source, "floor_heat_requested": self._floor_requested,
                "plugwise_zone": self.cfg[CONF_PLUGWISE], "pump": self.cfg[CONF_PUMP],
                "bathroom_zone_untouched": self.cfg.get(CONF_BATHROOM),
                "error": self._error, "simulation_mode": self.cfg.get(CONF_SIMULATION, True), "virtual_temperature": self.cfg.get(CONF_SIM_TEMP), "simulated_commands": self._simulated_commands[-8:], "strategy": "ac_first_plugwise_assist", "pump_control": "integration" if self.cfg.get(CONF_PUMP_MANAGED, False) else "plugwise_external"}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if previous:
            try:
                target = float(previous.attributes.get(ATTR_TEMPERATURE, 20))
                if self.min_temp <= target <= self.max_temp:
                    self._attr_target_temperature = target
            except (TypeError, ValueError):
                pass
        # Always restore OFF; never unexpectedly resume boiler demand.
        ids = [self.cfg[CONF_ROOM], self.cfg[CONF_AC], self.cfg[CONF_PLUGWISE], self.cfg[CONF_PUMP]]
        self._unsubs.append(async_track_state_change_event(self.hass, ids, self._state_changed))
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, timedelta(minutes=1)))
        # Do not command devices on startup until user explicitly selects HEAT.
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await super().async_will_remove_from_hass()

    @callback
    def _state_changed(self, event):
        if event.data.get("entity_id") == self.cfg[CONF_ROOM]:
            self.hass.async_create_task(self._control())
        else:
            self.async_write_ha_state()

    async def _tick(self, now):
        if self._attr_hvac_mode == HVACMode.HEAT:
            await self._control()

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode not in self.hvac_modes:
            raise ValueError("Unsupported HVAC mode")
        self._attr_hvac_mode = hvac_mode
        await self._control()

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            value = float(kwargs[ATTR_TEMPERATURE])
            if not self.min_temp <= value <= self.max_temp:
                raise ValueError("Target outside range")
            self._attr_target_temperature = value
        await self._control()

    def _fresh_temperature(self):
        state = self.hass.states.get(self.cfg[CONF_ROOM])
        temp = self.current_temperature
        if self.cfg.get(CONF_SIMULATION, True) and self.cfg.get(CONF_SIM_TEMP) is not None:
            return temp
        if temp is None or state is None or (dt_util.utcnow() - state.last_updated).total_seconds() > 1200:
            return None
        return temp

    def _valid(self, entity):
        state = self.hass.states.get(entity)
        return state if state is not None and state.state not in ("unavailable", "unknown") else None

    async def _command(self, domain, service, data):
        if self.cfg.get(CONF_SIMULATION, True):
            self._simulated_commands.append({"domain": domain, "service": service, **data})
            self._simulated_commands = self._simulated_commands[-8:]
            return
        await self.hass.services.async_call(domain, service, data, blocking=True)

    async def _set_climate_target(self, entity, target, *, force=False, kind="plugwise"):
        state = self._valid(entity)
        if state is None:
            raise RuntimeError(f"Climate unavailable: {entity}")
        current = state.attributes.get("temperature")
        last = self._last_plugwise_change if kind == "plugwise" else self._last_ac_change
        if current is not None and abs(float(current) - target) < 0.4:
            return
        if not force and monotonic() - last < 300:
            return
        await self._command("climate", "set_temperature", {"entity_id": entity, "temperature": target})
        if kind == "plugwise":
            self._last_plugwise_change = monotonic()
        else:
            self._last_ac_change = monotonic()

    async def _set_ac(self, enable, target):
        entity = self.cfg[CONF_AC]
        state = self._valid(entity)
        if state is None:
            raise RuntimeError("Airco unavailable")
        desired = HVACMode.HEAT if enable else HVACMode.OFF
        if state.state != desired:
            if enable and monotonic() - self._last_ac_change < 300:
                return
            await self._command("climate", "set_hvac_mode", {"entity_id": entity, "hvac_mode": desired})
            self._last_ac_change = monotonic()
        if enable:
            await self._set_climate_target(entity, target, kind="ac")

    async def _set_pump(self, enable, *, force=False):
        entity = self.cfg[CONF_PUMP]
        state = self._valid(entity)
        if state is None or state.state not in ("on", "off"):
            raise RuntimeError("Pump switch unavailable")
        current = state.state == "on"
        if current == enable:
            return
        elapsed = monotonic() - self._last_pump_change
        limit = 60 * self.cfg[CONF_MIN_ON if current else CONF_MIN_OFF]
        if not force and elapsed < limit:
            return
        await self._command("switch", "turn_on" if enable else "turn_off", {"entity_id": entity})
        self._last_pump_change = monotonic()

    async def _control(self):
        if self._busy:
            return
        self._busy = True
        try:
            self._simulated_commands = []
            temp = self._fresh_temperature()
            if self._attr_hvac_mode == HVACMode.OFF or temp is None:
                # Never switch off pump automatically on stale sensor: boiler may still
                # have residual heat. Withdraw Plugwise demand and leave pump as-is.
                plugwise = self._valid(self.cfg[CONF_PLUGWISE])
                if plugwise is not None and temp is not None:
                    await self._set_climate_target(self.cfg[CONF_PLUGWISE], max(5.0, temp - 3.0), force=True)
                await self._set_ac(False, self._attr_target_temperature)
                self._floor_requested = False
                self._source = "off" if self._attr_hvac_mode == HVACMode.OFF else "sensor_stale_manual_check"
                self._attr_hvac_action = HVACAction.OFF if self._attr_hvac_mode == HVACMode.OFF else HVACAction.IDLE
                return
            if not self._valid(self.cfg[CONF_PLUGWISE]) or (self.cfg.get(CONF_PUMP_MANAGED, False) and not self._valid(self.cfg[CONF_PUMP])):
                raise RuntimeError("Plugwise zone or pump unavailable")
            delta = self._attr_target_temperature - temp
            want_floor = (delta >= self.cfg[CONF_ASSIST]) if not self._floor_requested else (delta > 0.35)
            want_ac = delta > ( -0.15 if self._source in ("airco", "hybrid") else 0.25)
            # Heat demand only on the living-room Plugwise zone. Never alter bathroom.
            # No demand: set below measured temperature (not a boiler OFF command).
            plugwise_target = round((self._attr_target_temperature + 1.0) * 2) / 2 if want_floor else round(max(5.0, temp - 3.0) * 2) / 2
            # Start pump before asking boiler for heat.
            if want_floor and self.cfg.get(CONF_PUMP_MANAGED, False):
                await self._set_pump(True)
                if not self.cfg.get(CONF_SIMULATION, True) and self._valid(self.cfg[CONF_PUMP]).state != "on":
                    want_floor = False
                    plugwise_target = round(max(5.0, temp - 3.0) * 2) / 2
            await self._set_climate_target(self.cfg[CONF_PLUGWISE], plugwise_target)
            if not want_floor and self._floor_requested:
                self._pump_demand_ended = monotonic()
            if want_floor:
                self._pump_demand_ended = None
            self._floor_requested = want_floor
            if not want_floor and self._pump_demand_ended is not None:
                if monotonic() - self._pump_demand_ended >= self.cfg[CONF_POSTRUN] * 60:
                    # Cannot prove boiler has stopped: leave pump running by default.
                    # Manual/external pump safety automation required for shutdown.
                    self._pump_demand_ended = None
            await self._set_ac(want_ac, min(25.0, max(16.0, self._attr_target_temperature + 0.5)))
            self._source = "hybrid" if want_floor and want_ac else "floor" if want_floor else "airco" if want_ac else "idle"
            self._attr_hvac_action = HVACAction.HEATING if (want_floor or want_ac) else HVACAction.IDLE
            self._error = None
        except Exception as exc:
            _LOGGER.exception("Hybrid control error")
            self._error = str(exc)
            self._source = "error_manual_check"
            self._attr_hvac_action = HVACAction.IDLE
        finally:
            self._busy = False
            self.async_write_ha_state()
