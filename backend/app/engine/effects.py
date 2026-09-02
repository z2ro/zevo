from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class EffectExecutionContext:
    world: Any
    species: Any | None = None
    host: Any | None = None
    parasite: Any | None = None
    relation: Any | None = None
    event_context: Any | None = None
    event_service: Any | None = None


def _target(ctx: EffectExecutionContext, name: str):
    return {"world": ctx.world, "species": ctx.species, "host": ctx.host, "parasite": ctx.parasite}.get(name)


def execute_modify_population(effect, ctx: EffectExecutionContext):
    target = _target(ctx, effect.target)
    if target is None:
        raise ValueError(f"effect target '{effect.target}' is unavailable in execution context")
    before = target.population
    target.population = max(0, int(before * (effect.multiplier or 1.0)))
    return {"population_before": before, "population_after": target.population, "population_delta": target.population - before}


def execute_add_historical_flag(effect, ctx: EffectExecutionContext):
    target = _target(ctx, effect.target)
    if target is None or ctx.event_service is None or ctx.event_context is None:
        raise ValueError("historical flag effect requires target, event context, and event service")
    ctx.event_service.ensure_flag(ctx.event_context, effect.flag, species_id=getattr(target, "id", None),
                                  metadata={"parasite_species_id": getattr(ctx.parasite, "id", None)})
    return {"historical_flag": effect.flag}


EFFECT_HANDLERS: dict[str, Callable] = {
    "modify_population": execute_modify_population,
    "add_historical_flag": execute_add_historical_flag,
}


def execute_effect(effect, context: EffectExecutionContext):
    try:
        return EFFECT_HANDLERS[effect.type](effect, context)
    except KeyError as exc:
        raise ValueError(f"unknown effect type: {effect.type}") from exc


def execute_effects(effects, context: EffectExecutionContext):
    return [execute_effect(effect, context) for effect in effects]
