import pytest
from datetime import timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.entities import Habitat, Player, Species, SpeciesEvolution, World
from app.models.enums import EnergySource, EvolutionStatus, SpeciesStatus, SpeciesType, Strategy
from app.services.evolution_service import active_adaptive_response, adaptive_response_eligibility, combine_modifiers, complete_due_evolutions, pressures_for_species, start_evolution
from app.services.simulation_service import SimulationService
from app.simulation.population import update_population
from app.db.base import Base
from app.engine import CONTENT
from backend.tests.simulation.test_service import build_world


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def test_adaptive_response_deducts_resources_biases_then_completes_without_direct_trait(session):
    world_id, species_id, _ = build_world(session)
    species = session.get(Species, species_id)
    session.get(Habitat, species.habitat_id).solar_energy = 0
    biomass, trait = species.biomass, species.metabolic_efficiency
    start_evolution(session, 1, species_id, "METABOLIC_EFFICIENCY_I", 0)
    assert species.biomass < biomass
    bias, modifiers = active_adaptive_response(session, species_id, 1)
    assert bias.trait == "metabolic_efficiency"
    assert modifiers["reproduction_modifier"] == .95
    baseline = update_population(100, 1.5, 1_000, 50)
    adapted = update_population(100, 1.5, 1_000, 50, **modifiers)
    assert adapted.current < baseline.current
    complete_due_evolutions(session, world_id, 12_001)
    row = session.scalar(select(SpeciesEvolution).where(SpeciesEvolution.species_id == species_id))
    assert row.status is EvolutionStatus.COMPLETED
    assert species.metabolic_efficiency == trait
    expired_bias, expired_modifiers = active_adaptive_response(session, species_id, 12_001)
    assert expired_bias is None
    assert expired_modifiers == {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}


def test_focus_and_adaptive_tradeoffs_compose_multiplicatively():
    combined = combine_modifiers(
        {"reproduction_modifier": 1.2, "mortality_modifier": 1.15},
        {"reproduction_modifier": .9, "mortality_modifier": 1.0},
        {"reproduction_modifier": .5, "mortality_modifier": .8},
    )
    assert combined == {"reproduction_modifier": pytest.approx(.54), "mortality_modifier": pytest.approx(.92)}


def test_adaptive_response_is_active_for_exact_duration(session):
    world_id, species_id, _ = build_world(session)
    response = SpeciesEvolution(species_id=species_id, evolution_id="METABOLIC_EFFICIENCY_I", level=1,
                                status=EvolutionStatus.IN_PROGRESS, started_at_year=10_000, complete_at_year=13_000)
    session.add(response); session.flush()
    assert active_adaptive_response(session, species_id, 10_000)[0] is None
    for age in (11_000, 12_000, 13_000):
        bias, modifiers = active_adaptive_response(session, species_id, age)
        assert bias is not None and modifiers["reproduction_modifier"] == .95
    complete_due_evolutions(session, world_id, 13_000)
    assert response.status is EvolutionStatus.IN_PROGRESS
    assert active_adaptive_response(session, species_id, 14_000) == (None, {"reproduction_modifier": 1.0, "mortality_modifier": 1.0})
    complete_due_evolutions(session, world_id, 14_000)
    assert response.status is EvolutionStatus.COMPLETED


def test_competition_pressure_uses_ecological_context(session):
    _, species_id, _ = build_world(session)
    assert any(p.type == "COMPETITION" for p in pressures_for_species(session, session.get(Species, species_id)))


def test_tick_completes_adaptation_only_in_processed_world(session):
    world_a, species_a, _ = build_world(session)
    first = session.get(Species, species_a)
    session.get(Habitat, first.habitat_id).solar_energy = 0
    session.get(World, world_a).age_years = 12_000
    response_a = start_evolution(session, first.creator_id, first.id, "METABOLIC_EFFICIENCY_I", 0)
    other_world = World(name="Other", generation=0, tick=0, temperature=50, oxygen=1, co2=70, radiation=30, water_availability=80, average_ph=5, solar_energy=70, chemical_energy=60, geological_activity=50)
    session.add(other_world); session.flush()
    other_habitat = Habitat(world_id=other_world.id, name="Other", temperature=50, radiation=20, ph=5, water=90, solar_energy=90, chemical_energy=60, organic_resources=70, carrying_capacity=1_000)
    other_player = Player(username="Other")
    session.add_all([other_habitat, other_player]); session.flush()
    other = Species(name="Other", creator_id=other_player.id, habitat_id=other_habitat.id, species_type=SpeciesType.AUTOTROPH, status=SpeciesStatus.ACTIVE, is_player_controlled=True, population=100, strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR, thermal_tolerance=10, radiation_tolerance=10, ph_tolerance=10, metabolic_efficiency=10, reproduction_rate=10, mutation_rate=10, energy_efficiency=10, structural_resistance=10)
    session.add(other); session.flush()
    response_b = SpeciesEvolution(species_id=other.id, evolution_id="METABOLIC_EFFICIENCY_I", level=1, status=EvolutionStatus.IN_PROGRESS, started_at_year=0, complete_at_year=12_000)
    session.add(response_b); session.flush()
    service = SimulationService(Settings(database_url="", species_generations_per_simulation_step=1, simulation_random_seed=1))
    first_world = session.get(World, world_a)
    service.run_tick(session, world_a, now=first_world.last_simulated_at + timedelta(seconds=5))
    assert response_a.status is EvolutionStatus.COMPLETED
    assert response_b.status is EvolutionStatus.IN_PROGRESS


def test_resources_produce_during_tick(session):
    world_id, species_id, _ = build_world(session)
    species = session.get(Species, species_id)
    before = (species.biomass, species.energy, species.genetic_material)
    SimulationService(Settings(database_url="", species_generations_per_simulation_step=1, simulation_random_seed=1)).run_tick(session, world_id)
    assert (species.biomass, species.energy, species.genetic_material) > before


def test_completed_response_can_repeat_and_eligibility_explains_blocks(session):
    world_id, species_id, _ = build_world(session)
    species = session.get(Species, species_id)
    habitat = session.get(Habitat, species.habitat_id)
    habitat.solar_energy = 0; habitat.radiation = 100
    species.biomass = species.energy = species.genetic_material = 5_000
    metabolic = CONTENT["evolutions"]["METABOLIC_EFFICIENCY_I"]
    radiation = CONTENT["evolutions"]["RADIATION_SHIELDING_I"]
    assert adaptive_response_eligibility(session, species, metabolic) == (True, True, None)
    start_evolution(session, species.creator_id, species.id, metabolic.id, 0)
    assert adaptive_response_eligibility(session, species, radiation) == (True, False, "RESPONSE_ACTIVE")
    complete_due_evolutions(session, world_id, 12_001)
    assert adaptive_response_eligibility(session, species, metabolic) == (True, True, None)
    start_evolution(session, species.creator_id, species.id, metabolic.id, 14_000)
    assert len(list(session.scalars(select(SpeciesEvolution).where(
        SpeciesEvolution.species_id == species.id, SpeciesEvolution.evolution_id == metabolic.id,
    )))) == 2


def test_eligibility_distinguishes_pressure_and_resources(session):
    _, species_id, _ = build_world(session)
    species = session.get(Species, species_id)
    habitat = session.get(Habitat, species.habitat_id)
    metabolic = CONTENT["evolutions"]["METABOLIC_EFFICIENCY_I"]
    assert adaptive_response_eligibility(session, species, metabolic) == (False, False, "PRESSURE_INSUFFICIENT")
    habitat.solar_energy = 0; species.energy = 0
    assert adaptive_response_eligibility(session, species, metabolic) == (True, False, "INSUFFICIENT_RESOURCES")
