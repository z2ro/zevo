from types import SimpleNamespace

import pytest

from app.engine.effects import EffectExecutionContext, execute_effect
from app.engine.content import EffectSpec


def test_modify_population_and_missing_target():
    host = SimpleNamespace(population=1000)
    result = execute_effect(EffectSpec(type="modify_population", target="host", multiplier=.82), EffectExecutionContext(world=None, host=host))
    assert (host.population, result["population_delta"]) == (820, -180)
    with pytest.raises(ValueError):
        execute_effect(EffectSpec(type="modify_population", target="host", multiplier=.82), EffectExecutionContext(world=None))


def test_historical_flag_requires_service_context():
    effect = EffectSpec(type="add_historical_flag", target="host", flag="FLAG")
    with pytest.raises(ValueError):
        execute_effect(effect, EffectExecutionContext(world=None, host=SimpleNamespace(id=1)))
