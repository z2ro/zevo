from __future__ import annotations

from dataclasses import dataclass

from app.config.game_balance import BALANCE, BalanceConfig

from .common import clamp


@dataclass(frozen=True)
class PopulationResult:
    previous: int
    current: int
    births: int
    deaths: int
    delta: int


def update_population(
    population: int,
    fitness: float,
    carrying_capacity: int,
    reproduction_rate: int,
    *,
    balance: BalanceConfig = BALANCE,
    reproduction_modifier: float = 1.0,
    survival_modifier: float = 1.0,
) -> PopulationResult:
    if population <= 0:
        return PopulationResult(max(0, population), 0, 0, 0, 0)
    capacity = max(1, carrying_capacity)
    density = population / capacity
    # Above capacity the logistic term remains negative even for fit species.
    capacity_pressure = 1.0 - density
    responsiveness = balance.growth_responsiveness_base + balance.growth_reproduction_factor * clamp(reproduction_rate / 100.0, 0.0, 1.0)
    raw_rate = responsiveness * (fitness - 1.0) * capacity_pressure
    if density > 1.0:
        raw_rate -= min(balance.overcapacity_pressure_max, (density - 1.0) * balance.overcapacity_pressure_factor)
    rate = raw_rate * (reproduction_modifier if raw_rate >= 0 else survival_modifier)
    rate = clamp(rate, -balance.population_delta_limit, balance.population_delta_limit)
    delta = round(population * rate)
    # Carrying capacity applies smooth pressure without bypassing the absolute
    # per-tick delta bound for an already over-capacity population.
    current = max(0, population + delta)
    actual_delta = current - population
    return PopulationResult(
        previous=population,
        current=current,
        births=max(0, actual_delta),
        deaths=max(0, -actual_delta),
        delta=actual_delta,
    )
