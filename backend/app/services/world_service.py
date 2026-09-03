from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config.game_balance import HABITATS_INITIAL, WORLD_INITIAL
from app.models.entities import (
    GameEvent, Habitat, HistoricalFlag, PlayerAction, Species, SpeciesEvolution,
    SpeciesPopulationSnapshot, SpeciesRelation, SpeciesTraitHistory, World, WorldSnapshot,
)


def reset_world(session: Session, world_id: int, *, now: datetime | None = None) -> World:
    world = session.execute(select(World).where(World.id == world_id).with_for_update()).scalar_one()
    reset_at = now or datetime.now(timezone.utc)
    species_ids = select(Species.id).join(Habitat).where(Habitat.world_id == world.id)
    for model in (SpeciesRelation, PlayerAction, SpeciesEvolution, SpeciesPopulationSnapshot, SpeciesTraitHistory):
        if model is SpeciesRelation:
            session.execute(delete(model).where(
                model.predator_or_parasite_id.in_(species_ids) | model.target_species_id.in_(species_ids)))
        else:
            session.execute(delete(model).where(model.species_id.in_(species_ids)))
    session.execute(delete(GameEvent).where(GameEvent.world_id == world.id))
    session.execute(delete(HistoricalFlag).where(HistoricalFlag.world_id == world.id))
    session.execute(delete(WorldSnapshot).where(WorldSnapshot.world_id == world.id))
    session.execute(delete(Species).where(Species.id.in_(species_ids)))

    world.generation = 0  # Legacy internal column; no longer a public clock.
    world.tick = 0
    world.age_years = 0
    world.last_simulated_at = reset_at
    world.created_at = reset_at
    for key, value in WORLD_INITIAL.items():
        setattr(world, key, value)

    expected = {values[0]: values for values in HABITATS_INITIAL}
    habitats = {item.name: item for item in session.scalars(select(Habitat).where(Habitat.world_id == world.id))}
    for name, values in expected.items():
        _, temperature, radiation, ph, water, solar, chemical, organic, capacity = values
        habitat = habitats.get(name)
        if habitat is None:
            habitat = Habitat(world_id=world.id, name=name)
            session.add(habitat)
        habitat.temperature, habitat.radiation, habitat.ph = temperature, radiation, ph
        habitat.water, habitat.solar_energy, habitat.chemical_energy = water, solar, chemical
        habitat.organic_resources, habitat.carrying_capacity = organic, capacity
    for name, habitat in habitats.items():
        if name not in expected:
            session.delete(habitat)
    session.flush()
    return world
