from __future__ import annotations

import random
from dataclasses import dataclass

from app.config.game_balance import BALANCE, BalanceConfig
from app.models.enums import SpeciesStatus

from .evolution import TraitChange, attempt_mutation
from .fitness import FitnessContext, calculate_fitness
from .population import PopulationResult, update_population


@dataclass(frozen=True)
class SpeciesTickResult:
    species_id: int | None
    fitness: float
    population: PopulationResult
    mutation: TraitChange | None = None
    extinct: bool = False


def simulate_species(
    species: object,
    habitat: object,
    rng: random.Random,
    *,
    context: FitnessContext = FitnessContext(),
    balance: BalanceConfig = BALANCE,
    dev_mode: bool = False,
    reproduction_modifier: float = 1.0,
    survival_modifier: float = 1.0,
) -> SpeciesTickResult:
    fitness = calculate_fitness(species, habitat, context, balance=balance).value
    population = update_population(
        getattr(species, "population"), fitness, getattr(habitat, "carrying_capacity"),
        getattr(species, "reproduction_rate"), balance=balance,
        reproduction_modifier=reproduction_modifier, survival_modifier=survival_modifier,
    )
    species.fitness = fitness
    species.population = population.current
    mutation = attempt_mutation(species, habitat, rng, context, balance=balance, dev_mode=dev_mode)
    if mutation:
        fitness = mutation.fitness_after
        species.fitness = fitness
    extinct = species.population < balance.extinction_threshold
    if extinct:
        species.population = 0
        species.status = SpeciesStatus.EXTINCT
        species.is_player_controlled = False
        population = PopulationResult(
            previous=population.previous, current=0, births=population.births,
            deaths=population.previous, delta=-population.previous,
        )
    return SpeciesTickResult(getattr(species, "id", None), fitness, population, mutation, extinct)
