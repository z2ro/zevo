from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config.game_balance import HABITATS_INITIAL, WORLD_INITIAL
from app.config.settings import Settings
from app.db.base import Base
from app.db.bootstrap import bootstrap_world
from app.models.entities import (
    GameEvent, Habitat, HistoricalFlag, Player, PlayerAction, Species, SpeciesEvolution,
    SpeciesPopulationSnapshot, SpeciesRelation, SpeciesTraitHistory, World, WorldSnapshot,
)
from app.models.enums import ActionStatus, ActionType, EnergySource, EventRarity, EvolutionStatus, RelationType, SpeciesStatus, SpeciesType, Strategy, TraitChangeCause
from app.services.simulation_service import SimulationService
from app.services.world_service import reset_world


def _species(player_id, habitat_id, name, status=SpeciesStatus.ACTIVE):
    return Species(name=name, creator_id=player_id, habitat_id=habitat_id,
        species_type=SpeciesType.AUTOTROPH, status=status, is_player_controlled=status is SpeciesStatus.ACTIVE,
        population=100, generation=0, fitness=1, strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR,
        thermal_tolerance=10, radiation_tolerance=10, ph_tolerance=10, metabolic_efficiency=10,
        reproduction_rate=10, mutation_rate=10, energy_efficiency=10, structural_resistance=10)


def test_planet_age_uses_elapsed_wall_clock_and_generations_are_individual():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        world = World(name="Time", age_years=0, last_simulated_at=start, generation=0, tick=0,
            temperature=50, oxygen=1, co2=70, radiation=30, water_availability=80,
            average_ph=5, solar_energy=70, chemical_energy=60, geological_activity=50)
        session.add(world); session.flush()
        habitat = Habitat(world_id=world.id, name="Ocean", temperature=40, radiation=20, ph=5,
            water=90, solar_energy=90, chemical_energy=60, organic_resources=70, carrying_capacity=10_000)
        first_player, second_player = Player(username="First"), Player(username="Second")
        session.add_all([habitat, first_player, second_player]); session.flush()
        first = _species(first_player.id, habitat.id, "First")
        session.add(first); session.commit()
        service = SimulationService(Settings(database_url="", planet_years_per_real_second=200,
            species_generations_per_simulation_step=1_000, simulation_random_seed=1))
        service.run_tick(session, world.id, now=start + timedelta(seconds=7))
        second = _species(second_player.id, habitat.id, "Second")
        session.add(second); session.commit()
        service.run_tick(session, world.id, now=start + timedelta(seconds=12))
        assert world.age_years == 2_000
        assert first.generation == 2_000 and second.generation == 1_000
        first.status = SpeciesStatus.WILD; first.is_player_controlled = False
        second.status = SpeciesStatus.EXTINCT; second.is_player_controlled = False; second.population = 0
        service.run_tick(session, world.id, now=start + timedelta(seconds=17))
        assert first.generation == 3_000 and second.generation == 1_000


def test_partial_elapsed_time_is_preserved_and_early_calls_do_nothing():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        world = bootstrap_world(session)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        world.last_simulated_at = start
        player = session.scalar(select(Player).where(Player.username == "Zero"))
        habitat = session.scalar(select(Habitat).where(Habitat.world_id == world.id))
        species = _species(player.id, habitat.id, "Early")
        session.add(species); session.flush()
        resources = (species.biomass, species.energy, species.genetic_material)
        service = SimulationService(Settings(database_url="", simulation_random_seed=1))
        early = service.run_tick(session, world.id, now=start + timedelta(seconds=2))
        assert early.steps_processed == 0 and world.age_years == world.tick == 0
        assert species.generation == 0 and (species.biomass, species.energy, species.genetic_material) == resources
        first = service.run_tick(session, world.id, now=start + timedelta(seconds=7))
        assert first.steps_processed == 1 and world.age_years == 1_000 and world.tick == 1
        assert world.last_simulated_at.replace(tzinfo=timezone.utc) == start + timedelta(seconds=5)
        second = service.run_tick(session, world.id, now=start + timedelta(seconds=10))
        assert second.steps_processed == 1 and world.age_years == 2_000 and world.tick == 2
        assert species.generation == 2_000


def test_catchup_limit_preserves_backlog():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        world = bootstrap_world(session)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        world.last_simulated_at = start
        service = SimulationService(Settings(database_url="", max_catchup_steps=3, simulation_random_seed=1))
        now = start + timedelta(seconds=500)
        first = service.run_tick(session, world.id, now=now)
        assert first.steps_processed == 3 and world.age_years == 3_000
        assert world.last_simulated_at.replace(tzinfo=timezone.utc) == start + timedelta(seconds=15)
        second = service.run_tick(session, world.id, now=now)
        assert second.steps_processed == 3 and world.age_years == 6_000
        assert world.last_simulated_at.replace(tzinfo=timezone.utc) == start + timedelta(seconds=30)


def test_reset_world_clears_gameplay_and_restores_initial_state():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        world = bootstrap_world(session)
        players_before = session.scalar(select(func.count()).select_from(Player))
        habitat = session.scalar(select(Habitat).where(Habitat.world_id == world.id))
        players = list(session.scalars(select(Player).order_by(Player.id).limit(2)))
        first, second = _species(players[0].id, habitat.id, "A"), _species(players[1].id, habitat.id, "B", SpeciesStatus.WILD)
        session.add_all([first, second]); session.flush()
        session.add_all([
            SpeciesEvolution(species_id=first.id, evolution_id="CELLULAR_REPAIR_I", level=1, status=EvolutionStatus.IN_PROGRESS, started_at_year=0, complete_at_year=12_000),
            PlayerAction(player_id=players[0].id, species_id=first.id, action_type=ActionType.FOCUS_SURVIVAL, status=ActionStatus.PENDING, payload={}, execute_at_year=3_000),
            SpeciesPopulationSnapshot(species_id=first.id, generation=1_000, population=90, fitness=1, traits={}),
            SpeciesTraitHistory(species_id=first.id, generation=1_000, trait="thermal_tolerance", old_value=10, new_value=11, cause=TraitChangeCause.MUTATION),
            SpeciesRelation(predator_or_parasite_id=first.id, target_species_id=second.id, relation_type=RelationType.COMPETITION, strength=.2),
            GameEvent(world_id=world.id, code="RESET_TEST", name="Reset", description="Reset", rarity=EventRarity.COMMON, planet_age_years=2_000, historical=True, global_unique=False, repeat_scope="ALWAYS", event_metadata={}),
            HistoricalFlag(world_id=world.id, code="RESET_FLAG", planet_age_years=2_000),
            WorldSnapshot(world_id=world.id, age_years=2_000, tick=2, temperature=1, oxygen=2, co2=3, radiation=4),
        ])
        world.age_years = 2_000; world.tick = 2; world.temperature = -1; habitat.temperature = -1
        reset_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        reset_world(session, world.id, now=reset_at)
        reset_world(session, world.id, now=reset_at)
        assert world.age_years == world.tick == 0 and world.last_simulated_at.replace(tzinfo=timezone.utc) == reset_at
        assert world.temperature == WORLD_INITIAL["temperature"]
        assert session.scalar(select(func.count()).select_from(Player)) == players_before
        for model in (Species, SpeciesEvolution, PlayerAction, SpeciesPopulationSnapshot, SpeciesTraitHistory, SpeciesRelation, GameEvent, HistoricalFlag, WorldSnapshot):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        restored = list(session.scalars(select(Habitat).where(Habitat.world_id == world.id).order_by(Habitat.name)))
        assert len(restored) == len(HABITATS_INITIAL)
        expected_temperature = {row[0]: row[1] for row in HABITATS_INITIAL}
        assert all(item.temperature == expected_temperature[item.name] for item in restored)
