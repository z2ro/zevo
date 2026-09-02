from __future__ import annotations

import random
from types import SimpleNamespace

from app.models.entities import Habitat, Player, Species, SpeciesRelation, World
from app.models.enums import EnergySource, RelationType, SpeciesStatus, SpeciesType, Strategy
from app.simulation.fitness import calculate_fitness
from app.simulation.interactions import (
    competition_pressure,
    evaluate_parasitism,
    fitness_context_for,
    host_compatibility,
    persist_parasitism_relation,
    resource_overlap,
)


def species(**changes):
    values = dict(
        id=1, habitat_id=1, species_type=SpeciesType.AUTOTROPH,
        status=SpeciesStatus.ACTIVE, population=500, energy_source=EnergySource.SOLAR,
        strategy=Strategy.COLONIZER, thermal_tolerance=50, radiation_tolerance=20,
        ph_tolerance=50, metabolic_efficiency=60, reproduction_rate=70,
        mutation_rate=30, energy_efficiency=70, structural_resistance=40,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def habitat():
    return SimpleNamespace(
        temperature=50, radiation=20, ph=5, water=90, solar_energy=90,
        chemical_energy=60, organic_resources=70, carrying_capacity=1_000,
    )


def parasite(**changes):
    values = dict(
        id=10, species_type=SpeciesType.PARASITIC, energy_source=EnergySource.PARASITIC,
        strategy=Strategy.PARASITE, mutation_rate=90, metabolic_efficiency=80,
        reproduction_rate=90, energy_efficiency=90,
    )
    values.update(changes)
    return species(**values)


def test_resource_overlap_is_symmetric_and_separates_resource_pools():
    solar_a = species(id=1)
    solar_b = species(id=2)
    chemical = species(id=3, energy_source=EnergySource.CHEMICAL)
    assert resource_overlap(solar_a, solar_b) == 1.0
    assert resource_overlap(solar_a, chemical) == resource_overlap(chemical, solar_a)
    assert resource_overlap(solar_a, chemical) < 0.1


def test_competition_uses_population_metabolism_and_overlap():
    focal = species(id=1)
    low = species(id=2, population=100, metabolic_efficiency=20)
    high = species(id=3, population=900, metabolic_efficiency=100)
    unrelated = species(id=4, energy_source=EnergySource.CHEMICAL, population=20_000)
    extinct = species(id=5, status=SpeciesStatus.EXTINCT, population=20_000)
    low_result = competition_pressure(focal, [focal, low, unrelated, extinct], 1_000)
    high_result = competition_pressure(focal, [focal, high], 1_000)
    assert low_result.pressure == 0.02
    assert high_result.pressure == 0.9
    assert low_result.competitors == (2,)


def test_competition_pressure_reduces_fitness():
    focal = species(id=1)
    rival = species(id=2, population=1_000, metabolic_efficiency=100)
    base = calculate_fitness(focal, habitat()).value
    context = fitness_context_for(focal, [focal, rival], 1_000)
    assert context.competition == 1.0
    assert calculate_fitness(focal, habitat(), context).value < base


def test_host_requires_living_non_parasite_in_same_habitat():
    candidate = parasite()
    valid = species(id=2, population=1_000, structural_resistance=0)
    assert host_compatibility(candidate, valid).compatible
    assert not host_compatibility(candidate, species(id=3, habitat_id=2)).compatible
    assert not host_compatibility(candidate, species(id=4, status=SpeciesStatus.EXTINCT)).compatible
    assert not host_compatibility(candidate, parasite(id=11)).compatible


def test_host_compatibility_rewards_contact_and_is_bounded():
    candidate = parasite()
    resistant = species(id=2, population=10, structural_resistance=100, thermal_tolerance=0)
    vulnerable = species(id=3, population=10_000, structural_resistance=0, thermal_tolerance=50)
    weak = host_compatibility(candidate, resistant).score
    strong = host_compatibility(candidate, vulnerable, previous_contact=1.0).score
    assert 0 <= weak < strong <= 1


def test_parasite_without_host_gets_no_host_context_and_loses_fitness():
    candidate = parasite()
    no_host = fitness_context_for(candidate, [candidate], 1_000)
    with_host = fitness_context_for(candidate, [candidate, species(id=2, population=2_000)], 1_000)
    assert no_host.host_compatibility == 0
    assert calculate_fitness(candidate, habitat(), no_host).value < 1
    assert calculate_fitness(candidate, habitat(), with_host).value > calculate_fitness(candidate, habitat(), no_host).value


def test_parasitism_is_reproducible_with_injected_rng():
    candidate, host = parasite(), species(id=2, population=5_000, structural_resistance=0)
    left = evaluate_parasitism(candidate, host, random.Random(7))
    right = evaluate_parasitism(candidate, host, random.Random(7))
    assert left == right
    assert left.established
    assert left.strength > 0
    assert left.infection_rate > 0


def test_failed_roll_does_not_establish_relation():
    candidate = parasite(reproduction_rate=1, energy_efficiency=1)
    result = evaluate_parasitism(candidate, species(id=2), random.Random(0))
    assert not result.established
    assert result.strength == 0


def test_persist_relation_is_idempotent_and_refreshes_values(session):
    world = World(name="test", generation=0, tick=0, temperature=1, oxygen=1, co2=1,
                  radiation=1, water_availability=1, average_ph=7, solar_energy=1,
                  chemical_energy=1, geological_activity=1)
    player = Player(username="tester")
    session.add_all([world, player]); session.flush()
    home = Habitat(world_id=world.id, name="home", temperature=50, radiation=20, ph=5,
                   water=90, solar_energy=90, chemical_energy=60, organic_resources=70,
                   carrying_capacity=1_000)
    session.add(home); session.flush()
    common = dict(creator_id=player.id, habitat_id=home.id, population=500, generation=0,
                  fitness=1, thermal_tolerance=10, radiation_tolerance=10, ph_tolerance=10,
                  metabolic_efficiency=10, reproduction_rate=10, mutation_rate=10,
                  energy_efficiency=10, structural_resistance=10)
    db_parasite = Species(name="p", species_type=SpeciesType.PARASITIC,
                          strategy=Strategy.PARASITE, energy_source=EnergySource.PARASITIC,
                          status=SpeciesStatus.WILD, is_player_controlled=False, **common)
    db_host = Species(name="h", species_type=SpeciesType.AUTOTROPH,
                      strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR,
                      status=SpeciesStatus.ACTIVE, is_player_controlled=True, **common)
    session.add_all([db_parasite, db_host]); session.flush()
    result = evaluate_parasitism(db_parasite, db_host, random.Random(31), previous_contact=1.0)
    assert result.established
    first = persist_parasitism_relation(session, result)
    session.flush()
    second = persist_parasitism_relation(session, result)
    session.flush()
    assert first is second
    assert session.query(SpeciesRelation).count() == 1
    assert first.relation_type is RelationType.PARASITISM


def test_wild_parasite_remains_eligible():
    candidate = parasite(status=SpeciesStatus.WILD)
    result = evaluate_parasitism(candidate, species(id=2, population=5_000), random.Random(1))
    assert result.compatibility > 0
    assert result.established
