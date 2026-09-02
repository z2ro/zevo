from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE
from app.config.settings import Settings, get_settings
from app.models.entities import Habitat, Species, SpeciesPopulationSnapshot, SpeciesTraitHistory, World, WorldSnapshot
from app.models.enums import SpeciesStatus
from app.simulation.common import trait_values
from app.simulation.engine import simulate_species

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickSummary:
    world_id: int
    tick: int
    generation: int
    species_processed: int
    mutations: int
    extinctions: int


class SimulationService:
    """Transactional adapter around the pure simulation engine.

    The caller owns commit/rollback. PostgreSQL callers lock the world row, which
    serializes scheduler and DEV ticks without coupling the engine to FastAPI.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def run_tick(self, session: Session, world_id: int) -> TickSummary:
        world = session.execute(select(World).where(World.id == world_id).with_for_update()).scalar_one()
        next_tick = world.tick + 1
        seed = self.settings.simulation_random_seed
        rng = random.Random(f"{seed if seed is not None else 'zevo'}:{world.id}:{next_tick}")
        habitats = {h.id: h for h in session.scalars(select(Habitat).where(Habitat.world_id == world.id))}
        species_list = list(session.scalars(
            select(Species)
            .join(Habitat, Species.habitat_id == Habitat.id)
            .where(Habitat.world_id == world.id, Species.status != SpeciesStatus.EXTINCT)
            .order_by(Species.id)
        ))
        mutations = 0
        extinctions = 0
        generation = world.generation + self.settings.generations_per_tick

        for species in species_list:
            habitat = habitats[species.habitat_id]
            result = simulate_species(species, habitat, rng, dev_mode=self.settings.dev_mode)
            species.generation += self.settings.generations_per_tick
            if result.mutation:
                mutations += 1
                change = result.mutation
                session.add(SpeciesTraitHistory(
                    species_id=species.id, generation=species.generation, trait=change.trait,
                    old_value=change.old_value, new_value=change.new_value, cause=change.cause,
                ))
            if result.extinct:
                extinctions += 1
                species.extinct_at = datetime.now(timezone.utc)
                logger.info("species_extinct world_id=%s species_id=%s generation=%s", world.id, species.id, generation)
            session.add(SpeciesPopulationSnapshot(
                species_id=species.id, generation=species.generation, population=species.population,
                fitness=species.fitness, traits=trait_values(species),
            ))

        self._apply_species_environment(world, species_list)
        world.tick = next_tick
        world.generation = generation
        session.add(WorldSnapshot(
            world_id=world.id, generation=generation, tick=next_tick,
            temperature=world.temperature, oxygen=world.oxygen, co2=world.co2, radiation=world.radiation,
        ))
        session.flush()
        logger.info(
            "simulation_tick world_id=%s tick=%s generation=%s species=%s mutations=%s extinctions=%s",
            world.id, next_tick, generation, len(species_list), mutations, extinctions,
        )
        return TickSummary(world.id, next_tick, generation, len(species_list), mutations, extinctions)

    @staticmethod
    def _apply_species_environment(world: World, species_list: list[Species]) -> None:
        living_population = sum(max(0, s.population) for s in species_list)
        if not living_population:
            return
        solar = sum(s.population for s in species_list if str(getattr(s.energy_source, "value", s.energy_source)) == "SOLAR")
        chemical = sum(s.population for s in species_list if str(getattr(s.energy_source, "value", s.energy_source)) == "CHEMICAL")
        solar_share = solar / living_population
        chemical_share = chemical / living_population
        delta = BALANCE.environment_delta_limit
        world.oxygen = min(100.0, world.oxygen + delta * solar_share)
        world.co2 = max(0.0, world.co2 - delta * solar_share)
        world.chemical_energy = max(0.0, world.chemical_energy - delta * chemical_share)
