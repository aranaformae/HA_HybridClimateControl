import pytest

from custom_components.hybrid_climate_controller.engine import decide, finite


@pytest.mark.parametrize("value", [None, "unknown", "unavailable", "nan", "inf", -100, True])
def test_invalid_temperature(value):
    assert finite(value, -20, 60) is None
    assert decide(value, 20, True).source == "unavailable"


@pytest.mark.parametrize("room,source", [(18, "hybrid"), (19.5, "airco"), (20.5, "idle")])
def test_decisions(room, source):
    assert decide(room, 20, True).source == source


def test_off_and_hysteresis():
    assert decide(15, 20, False).ac_target is None
    assert decide(19.8, 20, True).source == "idle"
    assert decide(19.8, 20, True, "airco").source == "airco"
    assert decide(19.5, 20, True, "hybrid", True).cv_demand
