import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.entities import Habitat, Species, SpeciesEvolution
from app.models.enums import EvolutionStatus
from app.services.evolution_service import complete_due_evolutions, start_evolution
from app.services.simulation_service import SimulationService
from app.db.base import Base
from backend.tests.simulation.test_service import build_world


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def test_evolution_deducts_resources_and_applies_trait(session):
    world_id, species_id, _ = build_world(session)
    species = session.get(Species, species_id)
    session.get(Habitat, species.habitat_id).solar_energy = 0
    biomass, trait = species.biomass, species.metabolic_efficiency
    start_evolution(session, 1, species_id, "METABOLIC_EFFICIENCY_I", 0)
    assert species.biomass < biomass
    complete_due_evolutions(session, world_id, 12)
    row = session.scalar(select(SpeciesEvolution).where(SpeciesEvolution.species_id == species_id))
    assert row.status is EvolutionStatus.COMPLETED
    assert species.metabolic_efficiency == trait + 2


def test_resources_produce_during_tick(session):
    world_id, species_id, _ = build_world(session)
    species = session.get(Species, species_id)
    before = (species.biomass, species.energy, species.genetic_material)
    SimulationService(Settings(database_url="", generations_per_tick=1, simulation_random_seed=1)).run_tick(session, world_id)
    assert (species.biomass, species.energy, species.genetic_material) > before
