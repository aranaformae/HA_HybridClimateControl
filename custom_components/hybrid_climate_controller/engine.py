"""Pure advisory controller. No Home Assistant service access."""

from dataclasses import asdict, dataclass
from math import isfinite


def finite(value, minimum, maximum):
    """Reject booleans, NaN, infinity and values outside physical bounds."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return (
        number
        if not isinstance(value, bool) and isfinite(number) and minimum <= number <= maximum
        else None
    )


@dataclass(frozen=True)
class Decision:
    source: str
    reason: str
    deviation: float | None = None
    demand: float = 0
    ac_target: float | None = None
    plugwise_target: float | None = None
    cv_demand: bool = False

    def attributes(self):
        return asdict(self)


def decide(room, target, enabled, previous="off", floor=False, assist=1.0):
    """Original AC-first hysteresis, advisory only; demand is a proxy, not kW."""
    if not enabled:
        return Decision("off", "controller_off")
    room = finite(room, -20, 60)
    target = finite(target, 16, 25)
    if room is None or target is None:
        return Decision("unavailable", "invalid_or_stale_room_temperature")
    delta = target - room
    cv = delta > 0.35 if floor else delta >= assist
    ac = delta > (-0.15 if previous in ("airco", "hybrid") else 0.25)
    source = "hybrid" if cv and ac else "floor" if cv else "airco" if ac else "idle"
    return Decision(
        source,
        "cv_assistance" if cv else "ac_first" if ac else "target_satisfied",
        round(delta, 3),
        round(min(100, max(0, delta * 100)), 1),
        min(25, max(16, target + 0.5)) if ac else None,
        round((target + 1) * 2) / 2 if cv else round(max(5, room - 3) * 2) / 2,
        cv,
    )
