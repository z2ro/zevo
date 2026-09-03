from sqlalchemy import select

from app.config.settings import Settings
from app.models.entities import Habitat, Species, SpeciesRelation
from app.models.enums import EnergySource, SpeciesStatus, SpeciesType, Strategy
from app.services.simulation_service import SimulationService
from app.simulation.fitness import calculate_fitness
from test_service import build_world


def test_tick_applies_competition_from_preupdate_snapshot(session):
    world_id, active_id, wild_id = build_world(session)
    species = session.get(Species, active_id)
    without_competition = calculate_fitness(species, session.get(Habitat, species.habitat_id)).value
    service = SimulationService(Settings(database_url="", species_generations_per_simulation_step=1, simulation_random_seed=17))
    service.run_tick(session, world_id)
    assert session.get(Species, active_id).fitness < without_competition
    assert session.get(Species, active_id).fitness == session.get(Species, wild_id).fitness


def test_tick_establishes_relation_for_wild_parasite(session):
    world_id, active_id, wild_id = build_world(session)
    parasite = session.get(Species, wild_id)
    parasite.species_type = SpeciesType.PARASITIC
    parasite.energy_source = EnergySource.PARASITIC
    parasite.strategy = Strategy.PARASITE
    parasite.status = SpeciesStatus.WILD
    parasite.population = 5000
    for trait in ("thermal_tolerance", "radiation_tolerance", "ph_tolerance", "structural_resistance", "metabolic_efficiency"):
        setattr(parasite, trait, 0)
    parasite.mutation_rate = parasite.reproduction_rate = parasite.energy_efficiency = 25
    host = session.get(Species, active_id)
    host.population = 5000
    host.structural_resistance = 0
    service = SimulationService(Settings(database_url="", species_generations_per_simulation_step=1, simulation_random_seed=17))
    service.run_tick(session, world_id)
    relation = session.scalar(select(SpeciesRelation))
    assert relation and relation.predator_or_parasite_id == parasite.id
    assert parasite.fitness > 0
