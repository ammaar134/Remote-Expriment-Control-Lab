import pytest
from pydantic import ValidationError

from lab.filtering import EMA
from lab.models import Recipe


def test_recipe_tick_boundaries():
    with pytest.raises(ValidationError, match="whole sample periods"):
        Recipe(steps=[{"setpoint": 0.2, "duration_ms": 21}])
    with pytest.raises(ValidationError):
        Recipe(seed=True, steps=[{"setpoint": 0.2, "duration_ms": 20}])
    with pytest.raises(ValidationError):
        Recipe(steps=[{"setpoint": float("nan"), "duration_ms": 20}])
    with pytest.raises(ValidationError, match="sixty"):
        Recipe(steps=[{"setpoint": 0.2, "duration_ms": 60_000}] * 2)


def test_filter_initialization_lag_and_gaps():
    ema = EMA(0.25)
    assert ema.apply(0, 1.0) == 1.0
    assert ema.apply(1, 0.0) == 0.75
    with pytest.raises(ValueError, match="contiguous"):
        ema.apply(3, 0.0)
    assert ema.last_seq == 1
    assert ema.apply(2, 0.0) == 0.5625
    assert EMA(0.25).apply(0, 0.0) == 0.0
