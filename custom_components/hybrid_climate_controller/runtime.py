"""Entry-owned simulation state and bounded decision history."""

from collections import deque
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import CONF_ASSIST, CONF_ROOM, CONF_SIM_TEMP, DOMAIN
from .energy import PRICE_KEYS, energy_snapshot
from .engine import decide, finite

# Virtual inputs are scenario inputs, not measured values or learned parameters.
INPUTS = {
    "room_temperature": (5, 35, 0.1, 20, "°C"),
    "outdoor_temperature": (-30, 50, 0.1, 5, "°C"),
    "target_temperature": (16, 25, 0.5, 20, "°C"),
    "temperature_trend": (-10, 10, 0.1, 0, "°C/h"),
    "electricity_price": (-2, 5, 0.01, 0.30, "EUR/kWh"),
    "gas_price": (0, 10, 0.01, 1.30, "EUR/m³"),
    "cop": (1, 8, 0.1, 3, None),
    "floor_heat": (0, 100, 1, 0, "%"),
}


class SimulationRuntime:
    """Deliberately has no actuator/service interface in phases 1 and 2."""

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.cfg = {**entry.data, **entry.options}
        self.signal = f"{DOMAIN}_{entry.entry_id}"
        self.mode = self.cfg.get(
            "test_mode", "virtual" if self.cfg.get(CONF_SIM_TEMP) is not None else "dry_run"
        )
        if self.mode not in ("dry_run", "virtual"):
            self.mode = "dry_run"
        self.values = {key: spec[3] for key, spec in INPUTS.items()}
        self.values["room_temperature"] = finite(self.cfg.get(CONF_SIM_TEMP), 5, 35) or 20
        self.enabled = False
        self.target = 20.0
        self.history = deque(maxlen=50)
        self.decision = decide(None, self.target, False)
        self.energy = energy_snapshot(hass, self.cfg, self.mode, self.values)
        self.closed = False
        self.unsubs = []

    def start(self):
        self.unsubs = [
            async_track_state_change_event(
                self.hass,
                list(
                    dict.fromkeys(
                        filter(
                            None,
                            [
                                self.cfg[CONF_ROOM],
                                *(self.cfg.get(key) for key in PRICE_KEYS),
                                *self.cfg.get("future_price_entities", []),
                            ],
                        )
                    )
                ),
                self._changed,
            ),
            async_track_time_interval(self.hass, self._tick, timedelta(minutes=1)),
        ]

    def close(self):
        self.closed = True
        for unsub in self.unsubs:
            unsub()
        self.unsubs.clear()

    @callback
    def _changed(self, event):
        self.evaluate()

    async def _tick(self, now):
        self.evaluate()

    @property
    def measured_temperature(self):
        state = self.hass.states.get(self.cfg[CONF_ROOM])
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        # last_reported accepts unchanged but freshly reported temperatures.
        reported = getattr(state, "last_reported", state.last_updated)
        if (dt_util.utcnow() - reported).total_seconds() > 1200:
            return None
        unit = state.attributes.get(
            "temperature_unit" if state.domain == "climate" else "unit_of_measurement", "°C"
        )
        if unit != "°C":
            return None
        return finite(
            state.attributes.get("current_temperature")
            if state.domain == "climate"
            else state.state,
            -20,
            60,
        )

    @property
    def room(self):
        return (
            self.values["room_temperature"] if self.mode == "virtual" else self.measured_temperature
        )

    def set_value(self, key, value):
        spec = INPUTS[key]
        value = finite(value, spec[0], spec[1])
        if value is None:
            raise ValueError("Invalid virtual value")
        self.values[key] = value
        self.evaluate()

    def set_mode(self, mode):
        if mode not in ("dry_run", "virtual"):
            raise ValueError("Physical control is not available in this test build")
        self.mode = mode
        self.enabled = False  # Explicitly re-enable advisory HEAT after changing mode.
        self.evaluate()

    def evaluate(self):
        if self.closed:
            return
        target = self.values["target_temperature"] if self.mode == "virtual" else self.target
        new = decide(
            self.room,
            target,
            self.enabled,
            self.decision.source,
            self.decision.cv_demand,
            self.cfg.get(CONF_ASSIST, 1.0),
        )
        self.energy = energy_snapshot(self.hass, self.cfg, self.mode, self.values)
        snapshot = {
            "energy": {
                key: value
                for key, value in self.energy.items()
                if key != "future_electricity_prices"
            },
            "mode": self.mode,
            "enabled": self.enabled,
            "room": self.room,
            "target": target,
            "virtual_inputs": dict(self.values) if self.mode == "virtual" else None,
            **new.attributes(),
        }
        if not self.history or any(
            self.history[-1].get(key) != value for key, value in snapshot.items()
        ):
            self.history.append(
                {
                    "time": dt_util.utcnow().isoformat(),
                    **snapshot,
                    "input_origin": "virtual" if self.mode == "virtual" else "measured",
                    **new.attributes(),
                }
            )
        self.decision = new
        async_dispatcher_send(self.hass, self.signal)
