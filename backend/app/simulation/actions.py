from __future__ import annotations

import random
from dataclasses import dataclass

from app.config.game_balance import BALANCE, TRAIT_NAMES, BalanceConfig
from app.engine import CONTENT


@dataclass(frozen=True)
class FounderChange:
    trait: str
    old_value: int
    new_value: int


def migration_population(population: int, *, balance: BalanceConfig = BALANCE) -> int:
    """All population migrates; only configured transit mortality is applied."""
    return max(0, round(population * (1.0 - balance.migration_mortality)))


def split_population(population: int, fraction: float, *, balance: BalanceConfig = BALANCE) -> int:
    """Keep an aggregate population while charging mortality to the split cohort."""
    losses = round(population * fraction * balance.split_mortality)
    return max(0, population - losses)


def apply_founder_effect(
    species: object,
    rng: random.Random,
    *,
    balance: BalanceConfig = BALANCE,
) -> list[FounderChange]:
    changes: list[FounderChange] = []
    target_count = rng.randint(1, 2)
    candidates = list(TRAIT_NAMES)
    rng.shuffle(candidates)
    for trait in candidates:
        if len(changes) >= target_count:
            break
        old = int(getattr(species, trait))
        magnitude = rng.randint(1, 2)
        total = sum(int(getattr(species, name)) for name in TRAIT_NAMES)
        possible: list[int] = []
        lower = max(balance.trait_min, old - magnitude)
        upper = min(balance.trait_max, old + magnitude)
        if lower != old:
            possible.append(lower)
        if upper != old and total - old + upper <= balance.trait_budget:
            possible.append(upper)
        if not possible:
            continue
        candidate = rng.choice(possible)
        setattr(species, trait, candidate)
        changes.append(FounderChange(trait, old, candidate))
    return changes


def focus_modifiers(action_type: str) -> dict[str, float]:
    definition = CONTENT["actions"].get(action_type.lower())
    if definition is None:
        raise ValueError(f"Unsupported focus action: {action_type}")
    return dict(definition.modifiers)


def focus_duration(action_type: str) -> int:
    definition = CONTENT["actions"].get(action_type.lower())
    if definition is None or definition.duration_ticks is None:
        raise ValueError(f"Unsupported focus action: {action_type}")
    return definition.duration_ticks
