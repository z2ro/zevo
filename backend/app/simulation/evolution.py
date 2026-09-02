from __future__ import annotations

import random
from dataclasses import dataclass

from app.config.game_balance import BALANCE, TRAIT_NAMES, BalanceConfig
from app.models.enums import TraitChangeCause

from .fitness import FitnessContext, calculate_fitness


@dataclass(frozen=True)
class TraitChange:
    trait: str
    old_value: int
    new_value: int
    cause: TraitChangeCause
    fitness_before: float
    fitness_after: float


def attempt_mutation(
    species: object,
    habitat: object,
    rng: random.Random,
    context: FitnessContext = FitnessContext(),
    *,
    balance: BalanceConfig = BALANCE,
    dev_mode: bool = False,
    force: bool = False,
) -> TraitChange | None:
    chance = balance.mutation_chance * (1.0 + getattr(species, "mutation_rate") / 100.0)
    if dev_mode:
        chance *= balance.dev_mutation_multiplier
    if not force and rng.random() >= min(1.0, chance):
        return None

    trait = rng.choice(TRAIT_NAMES)
    old = int(getattr(species, trait))
    magnitude_range = balance.bottleneck_mutation_magnitude if getattr(species, "population") < balance.bottleneck_population else balance.mutation_magnitude
    direction = rng.choice((-1, 1))
    candidate = max(balance.trait_min, min(balance.trait_max, old + direction * rng.randint(*magnitude_range)))
    current_total = sum(int(getattr(species, name)) for name in TRAIT_NAMES)
    if current_total - old + candidate > balance.trait_budget:
        # Preserve the persistence invariant while allowing redistribution/loss.
        candidate = max(balance.trait_min, old - abs(candidate - old))
    if candidate == old:
        return None

    before = calculate_fitness(species, habitat, context, balance=balance).value
    setattr(species, trait, candidate)
    after = calculate_fitness(species, habitat, context, balance=balance).value
    delta = after - before
    fixation = (
        balance.beneficial_fixation_chance if delta > balance.selection_beneficial_threshold
        else balance.neutral_fixation_chance if delta >= balance.selection_harmful_threshold
        else balance.harmful_fixation_chance
    )
    if not force and rng.random() >= fixation:
        setattr(species, trait, old)
        return None
    cause = TraitChangeCause.SELECTION if abs(delta) > balance.selection_beneficial_threshold else TraitChangeCause.MUTATION
    return TraitChange(trait, old, candidate, cause, before, after)
