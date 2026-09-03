from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.config.settings import Settings
from app.models.entities import Habitat, Player, Species, SpeciesPopulationSnapshot, SpeciesTraitHistory, World, WorldSnapshot
from app.models.enums import EnergySource, SpeciesStatus, SpeciesType, Strategy
from app.services.simulation_service import SimulationService


def build_world(session):
    world = World(name="Eos-test", generation=0, tick=0, temperature=50, oxygen=1, co2=70,
                  radiation=30, water_availability=80, average_ph=5, solar_energy=70,
                  chemical_energy=60, geological_activity=50)
    session.add(world); session.flush()
    habitat = Habitat(world_id=world.id, name="Ocean", temperature=40, radiation=20, ph=5,
                      water=90, solar_energy=90, chemical_energy=60, organic_resources=70,
                      carrying_capacity=10_000)
    player = Player(username="Zero")
    session.add_all([habitat, player]); session.flush()
    common = dict(creator_id=player.id, habitat_id=habitat.id, species_type=SpeciesType.AUTOTROPH,
                  strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR,
                  population=100, thermal_tolerance=10, radiation_tolerance=10, ph_tolerance=10,
                  metabolic_efficiency=10, reproduction_rate=10, mutation_rate=10,
                  energy_efficiency=10, structural_resistance=10)
    active = Species(name="Active", status=SpeciesStatus.ACTIVE, is_player_controlled=True, **common)
    wild = Species(name="Legacy", status=SpeciesStatus.WILD, is_player_controlled=False, **common)
    session.add_all([active, wild]); session.commit()
    return world.id, active.id, wild.id


def test_tick_persists_snapshots_advances_active_and_wild(session):
    world_id, active_id, wild_id = build_world(session)
    service = SimulationService(Settings(database_url="", species_generations_per_simulation_step=1_000,
                                         simulation_random_seed=7, dev_mode=False))
    initial = session.get(World, world_id).last_simulated_at
    summary = service.run_tick(session, world_id, now=initial + timedelta(seconds=5))
    session.commit()
    world = session.get(World, world_id)
    active, wild = session.get(Species, active_id), session.get(Species, wild_id)
    assert summary.species_processed == 2
    assert (world.tick, world.age_years) == (1, 1_000)
    assert active.generation == wild.generation == 1_000
    assert active.population != 100 and wild.population != 100
    assert len(list(session.scalars(select(SpeciesPopulationSnapshot)))) == 2
    assert len(list(session.scalars(select(WorldSnapshot)))) == 1


def test_same_seed_and_state_produce_same_tick(session):
    world_id, active_id, wild_id = build_world(session)
    settings = Settings(database_url="", species_generations_per_simulation_step=1_000, simulation_random_seed=99, dev_mode=True)
    now = session.get(World, world_id).last_simulated_at + timedelta(seconds=5)
    SimulationService(settings).run_tick(session, world_id, now=now)
    first = [(s.id, s.population, s.fitness, s.thermal_tolerance, s.mutation_rate)
             for s in session.scalars(select(Species).order_by(Species.id))]
    session.rollback()
    # rollback restores the exact pre-tick database state; identity map is expired.
    SimulationService(settings).run_tick(session, world_id, now=now)
    second = [(s.id, s.population, s.fitness, s.thermal_tolerance, s.mutation_rate)
              for s in session.scalars(select(Species).order_by(Species.id))]
    assert first == second


def test_dev_tick_records_selected_mutation_history(session):
    world_id, *_ = build_world(session)
    settings = Settings(database_url="", species_generations_per_simulation_step=1_000, simulation_random_seed=2, dev_mode=True)
    service = SimulationService(settings)
    now = session.get(World, world_id).last_simulated_at
    for _ in range(12):
        now += timedelta(seconds=5); service.run_tick(session, world_id, now=now)
    histories = list(session.scalars(select(SpeciesTraitHistory)))
    assert histories
    assert all(change.old_value != change.new_value for change in histories)


def test_tick_isolated_to_requested_world(session):
    first_world, active_id, wild_id = build_world(session)
    other_world = World(name="Other", generation=0, tick=0, temperature=30, oxygen=2, co2=60,
                        radiation=10, water_availability=90, average_ph=7, solar_energy=60,
                        chemical_energy=50, geological_activity=20)
    session.add(other_world); session.flush()
    other_habitat = Habitat(world_id=other_world.id, name="Other Ocean", temperature=30,
                            radiation=10, ph=7, water=90, solar_energy=60, chemical_energy=50,
                            organic_resources=60, carrying_capacity=2_000)
    other_player = Player(username="OtherPlayer")
    session.add_all([other_habitat, other_player]); session.flush()
    other_species = Species(
        name="Outsider", creator_id=other_player.id, habitat_id=other_habitat.id,
        species_type=SpeciesType.AUTOTROPH, status=SpeciesStatus.ACTIVE,
        is_player_controlled=True, population=100, strategy=Strategy.COLONIZER,
        energy_source=EnergySource.SOLAR, thermal_tolerance=10, radiation_tolerance=10,
        ph_tolerance=10, metabolic_efficiency=10, reproduction_rate=10, mutation_rate=10,
        energy_efficiency=10, structural_resistance=10,
    )
    session.add(other_species); session.commit()

    first = session.get(World, first_world)
    summary = SimulationService(Settings(database_url="", species_generations_per_simulation_step=1_000,
                                          simulation_random_seed=3)).run_tick(session, first_world, now=first.last_simulated_at + timedelta(seconds=5))
    assert summary.species_processed == 2
    assert session.get(Species, active_id).generation == 1_000
    assert session.get(Species, wild_id).generation == 1_000
    assert session.get(Species, other_species.id).generation == 0
    assert session.get(World, other_world.id).tick == 0


def test_snapshot_fitness_matches_post_mutation_traits(session):
    world_id, *_ = build_world(session)
    settings = Settings(database_url="", species_generations_per_simulation_step=1_000,
                        simulation_random_seed=2, dev_mode=True)
    service = SimulationService(settings)
    now = session.get(World, world_id).last_simulated_at
    for _ in range(12):
        now += timedelta(seconds=5); service.run_tick(session, world_id, now=now)
    latest = session.scalars(
        select(SpeciesPopulationSnapshot).order_by(SpeciesPopulationSnapshot.id.desc())
    ).first()
    current = session.get(Species, latest.species_id)
    assert latest.fitness == current.fitness
    assert latest.traits == {
        name: getattr(current, name) for name in latest.traits
    }
