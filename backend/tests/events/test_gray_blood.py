from random import Random
from sqlalchemy import select
from app.events.definitions import evaluate_tick_events
from app.models.entities import GameEvent, Species, SpeciesRelation, World
from app.models.enums import EnergySource, RelationType, SpeciesStatus, SpeciesType, Strategy
from backend.tests.simulation.test_service import build_world
from backend.tests.simulation.conftest import session  # noqa: F401


def test_gray_blood_accepts_wild_parasite_and_persists_metadata(session):
    world_id, host_id, parasite_id = build_world(session)
    world, host, parasite = session.get(World, world_id), session.get(Species, host_id), session.get(Species, parasite_id)
    parasite.species_type, parasite.energy_source, parasite.strategy = SpeciesType.PARASITIC, EnergySource.PARASITIC, Strategy.PARASITE
    parasite.status, parasite.mutation_rate = SpeciesStatus.WILD, 30
    host.population = 2000
    session.add(SpeciesRelation(predator_or_parasite_id=parasite.id, target_species_id=host.id,
        relation_type=RelationType.PARASITISM, strength=.8, infection_rate=.4, virulence=.4, transmission_rate=.4))
    session.flush(); before = host.population
    assert evaluate_tick_events(session, world, [host, parasite], Random(1), True, {}) >= 1
    event = session.scalar(select(GameEvent).where(GameEvent.code == "GRAY_BLOOD"))
    assert event.event_metadata["parasite_species_id"] == parasite.id and host.population < before
