from __future__ import annotations

import random
from dataclasses import replace
from types import SimpleNamespace

from app.models.enums import EnergySource, SpeciesStatus, SpeciesType, Strategy
from app.config.game_balance import BALANCE
from app.simulation.engine import simulate_species
from app.simulation.evolution import attempt_mutation
from app.simulation.fitness import FitnessContext, calculate_fitness, preview_fitness
from app.simulation.population import update_population


def habitat(**changes):
    values = dict(temperature=50, radiation=20, ph=5, water=90, solar_energy=90,
                  chemical_energy=60, organic_resources=70, carrying_capacity=1_000)
    values.update(changes)
    return SimpleNamespace(**values)


def species(**changes):
    values = dict(id=1, species_type=SpeciesType.AUTOTROPH, status=SpeciesStatus.ACTIVE,
                  is_player_controlled=True, population=100, fitness=1.0,
                  strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR,
                  thermal_tolerance=50, radiation_tolerance=20, ph_tolerance=50,
                  metabolic_efficiency=70, reproduction_rate=70, mutation_rate=20,
                  energy_efficiency=70, structural_resistance=60)
    values.update(changes)
    return SimpleNamespace(**values)


def test_preview_uses_fitness_and_hides_internal_components():
    result = preview_fitness(species(), habitat())
    assert result["estimated_fitness"] > 1
    assert result["estimated_growth"] == "positive"
    assert set(result) == {"estimated_fitness", "estimated_growth", "risk", "environment_compatibility"}


def test_good_environment_grows_and_hostile_environment_declines():
    fit = calculate_fitness(species(), habitat()).value
    hostile = calculate_fitness(
        species(thermal_tolerance=0, radiation_tolerance=0, ph_tolerance=0,
                metabolic_efficiency=0, reproduction_rate=0, energy_efficiency=0,
                structural_resistance=0),
        habitat(temperature=100, radiation=100, ph=10, water=0, solar_energy=0),
    ).value
    assert fit > 1
    assert hostile < 1
    assert update_population(100, fit, 1_000, 70).delta > 0
    assert update_population(100, hostile, 1_000, 10).delta < 0


def test_focus_modifiers_change_population_without_mutating_traits():
    fit = calculate_fitness(species(), habitat()).value
    baseline = update_population(500, fit, 1_000, 70)
    reproduction = update_population(500, fit, 1_000, 70, reproduction_modifier=1.2, survival_modifier=.8)
    survival = update_population(500, fit, 1_000, 70, reproduction_modifier=.8, survival_modifier=1.2)
    assert reproduction.current > baseline.current > survival.current


def test_carrying_capacity_caps_growth_and_delta_is_bounded():
    result = update_population(990, 2.5, 1_000, 100)
    assert result.current <= 1_000
    above_capacity = update_population(2_000, 2.5, 1_000, 100)
    assert above_capacity.current > 1_000
    assert abs(above_capacity.delta) <= round(2_000 * BALANCE.population_delta_limit)
    assert abs(update_population(100, 0, 1_000, 100).delta) <= 35


def test_parasite_without_host_loses_fitness():
    parasite = species(species_type=SpeciesType.PARASITIC, strategy=Strategy.PARASITE,
                       energy_source=EnergySource.PARASITIC)
    without = calculate_fitness(parasite, habitat()).value
    with_host = calculate_fitness(parasite, habitat(), FitnessContext(host_compatibility=0.9)).value
    assert without < 1
    assert with_host > without


def test_forced_mutation_changes_a_trait_and_is_reproducible():
    left, right = species(), species()
    a = attempt_mutation(left, habitat(), random.Random(42), force=True)
    b = attempt_mutation(right, habitat(), random.Random(42), force=True)
    assert a is not None
    assert a == b
    assert getattr(left, a.trait) == a.new_value != a.old_value


def test_bottleneck_can_produce_larger_mutation():
    observed = []
    for seed in range(30):
        candidate = species(population=10)
        change = attempt_mutation(candidate, habitat(), random.Random(seed), force=True)
        if change:
            observed.append(abs(change.new_value - change.old_value))
    assert max(observed) > 3


def test_mutation_preserves_persistent_trait_budget():
    at_budget = species(thermal_tolerance=20, radiation_tolerance=10, ph_tolerance=10,
                        metabolic_efficiency=15, reproduction_rate=15, mutation_rate=10,
                        energy_efficiency=10, structural_resistance=10)
    change = attempt_mutation(at_budget, habitat(), random.Random(0), force=True)
    assert change is not None
    names = ("thermal_tolerance", "radiation_tolerance", "ph_tolerance", "metabolic_efficiency",
             "reproduction_rate", "mutation_rate", "energy_efficiency", "structural_resistance")
    assert sum(getattr(at_budget, name) for name in names) <= 100


def test_selection_uses_injected_balance_for_before_and_after_fitness():
    custom = replace(BALANCE, fitness_max=0.1)
    change = attempt_mutation(species(), habitat(), random.Random(42), balance=custom, force=True)
    assert change is not None
    assert change.fitness_before <= 0.1
    assert change.fitness_after <= 0.1


def test_extinction_is_irreversible_state_and_clears_control():
    dying = species(population=1)
    result = simulate_species(dying, habitat(), random.Random(1))
    assert result.extinct
    assert dying.population == 0
    assert dying.status is SpeciesStatus.EXTINCT
    assert dying.is_player_controlled is False


def test_wild_species_uses_the_same_simulation_path():
    wild = species(status=SpeciesStatus.WILD, is_player_controlled=False)
    old_population = wild.population
    result = simulate_species(wild, habitat(), random.Random(1))
    assert result.species_id == wild.id
    assert wild.population > old_population
