from __future__ import annotations

import random
from dataclasses import dataclass

from app.config.game_balance import BALANCE, TRAIT_NAMES, BalanceConfig


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


def focus_modifiers(action_type: str, *, balance: BalanceConfig = BALANCE) -> dict[str, float]:
    if action_type == "FOCUS_REPRODUCTION":
        return {"reproduction": 1.0 + balance.focus_bonus, "survival": 1.0 - balance.focus_penalty}
    if action_type == "FOCUS_SURVIVAL":
        return {"reproduction": 1.0 - balance.focus_penalty, "survival": 1.0 + balance.focus_bonus}
    raise ValueError(f"Unsupported focus action: {action_type}")
