from __future__ import annotations

import logging
import random
from copy import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE
from app.config.settings import Settings, get_settings
from app.models.entities import Habitat, Species, SpeciesPopulationSnapshot, SpeciesTraitHistory, World, WorldSnapshot
from app.models.enums import SpeciesStatus
from app.simulation.common import trait_values
from app.simulation.engine import simulate_species
from app.simulation.interactions import evaluate_parasitism, fitness_context_for, host_compatibility, persist_parasitism_relation
from app.simulation.common import enum_value
from app.events.definitions import evaluate_tick_events
from app.simulation.bots import run_bots
from app.services.action_service import active_focus_modifiers, complete_due_focuses, complete_due_migrations
from app.services.evolution_service import active_adaptive_response, combine_modifiers, complete_due_evolutions

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimulationSummary:
    world_id: int
    steps_processed: int
    simulation_step: int
    planet_age_years: int
    species_processed: int
    mutations: int
    extinctions: int


class SimulationService:
    """Transactional adapter around the pure simulation engine.

    The caller owns commit/rollback. PostgreSQL callers lock the world row, which
    serializes scheduler and DEV simulation steps without coupling the engine to FastAPI.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def run_tick(self, session: Session, world_id: int, *, now: datetime | None = None) -> SimulationSummary:
        """Process the bounded number of complete real-time intervals now due."""
        world = session.execute(select(World).where(World.id == world_id).with_for_update()).scalar_one()
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        previous = world.last_simulated_at
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        elapsed_seconds = max(0.0, (now - previous).total_seconds())
        steps_due = int(elapsed_seconds / self.settings.simulation_interval_seconds)
        return self._run_steps(world, min(steps_due, self.settings.max_catchup_steps))

    def run_steps(self, session: Session, world_id: int, steps: int) -> SimulationSummary:
        """Run an exact number of steps for the DEV simulation endpoint."""
        world = session.execute(select(World).where(World.id == world_id).with_for_update()).scalar_one()
        return self._run_steps(world, steps)

    def _run_steps(self, world: World, steps: int) -> SimulationSummary:
        processed = species_processed = mutations = extinctions = 0
        years_per_step = round(self.settings.simulation_interval_seconds * self.settings.planet_years_per_real_second)
        for _ in range(steps):
            world.age_years += years_per_step
            world.last_simulated_at += timedelta(seconds=self.settings.simulation_interval_seconds)
            step_species, step_mutations, step_extinctions = self._process_simulation_step(world)
            species_processed += step_species
            mutations += step_mutations
            extinctions += step_extinctions
            processed += 1
        return SimulationSummary(world.id, processed, world.tick, world.age_years,
                                 species_processed, mutations, extinctions)

    def _process_simulation_step(self, world: World) -> tuple[int, int, int]:
        session = Session.object_session(world)
        if session is None:
            raise RuntimeError("world must be attached to a session")
        next_tick = world.tick + 1
        seed = self.settings.simulation_random_seed
        rng = random.Random(f"{seed if seed is not None else 'zevo'}:{world.id}:{next_tick}")
        world.tick = next_tick
        complete_due_migrations(session, world.id, world.age_years)
        complete_due_focuses(session, world.id, world.age_years)
        run_bots(session, world, rng)
        habitats = {h.id: h for h in session.scalars(select(Habitat).where(Habitat.world_id == world.id))}
        species_list = list(session.scalars(
            select(Species)
            .join(Habitat, Species.habitat_id == Habitat.id)
            .where(Habitat.world_id == world.id, Species.status != SpeciesStatus.EXTINCT)
            .order_by(Species.id)
        ))
        mutations = 0
        mutation_results = {}
        extinctions = 0
        # Every species sees the same pre-update ecosystem, independent of DB order.
        snapshot = tuple(copy(species) for species in species_list)
        contexts = {
            species.id: fitness_context_for(species, snapshot, habitats[species.habitat_id].carrying_capacity)
            for species in snapshot
        }

        for parasite in snapshot:
            if enum_value(parasite.species_type) != "PARASITIC":
                continue
            hosts = sorted(
                (host for host in snapshot if host_compatibility(parasite, host).compatible),
                key=lambda host: host_compatibility(parasite, host).score,
                reverse=True,
            )
            if hosts:
                persist_parasitism_relation(session, evaluate_parasitism(parasite, hosts[0], rng))

        for species in species_list:
            species.biomass += max(1, round(species.population * max(0.0, species.fitness) * BALANCE.resource_biomass_rate))
            species.energy += max(1, round(species.population * max(0.0, species.fitness) * BALANCE.resource_energy_rate))
            species.genetic_material += max(1, round(species.population * max(0.0, species.fitness) * BALANCE.resource_genetic_rate))
            habitat = habitats[species.habitat_id]
            focus = active_focus_modifiers(session, species.id, world.age_years)
            bias, adaptive = active_adaptive_response(session, species.id, world.age_years)
            modifiers = combine_modifiers(focus, adaptive)
            result = simulate_species(
                species, habitat, rng, context=contexts[species.id], dev_mode=self.settings.dev_mode,
                reproduction_modifier=modifiers["reproduction_modifier"],
                mortality_modifier=modifiers["mortality_modifier"],
                mutation_bias=bias,
            )
            species.generation += self.settings.species_generations_per_simulation_step
            if result.mutation:
                mutations += 1
                mutation_results[species.id] = result.mutation
                change = result.mutation
                session.add(SpeciesTraitHistory(
                    species_id=species.id, generation=species.generation, trait=change.trait,
                    old_value=change.old_value, new_value=change.new_value, cause=change.cause,
                ))
            if result.extinct:
                extinctions += 1
                species.extinct_at = datetime.now(timezone.utc)
                logger.info("species_extinct world_id=%s species_id=%s generation=%s", world.id, species.id, species.generation)
        complete_due_evolutions(session, world.id, world.age_years)
        self._apply_species_environment(world, species_list)
        evaluate_tick_events(session, world, species_list, rng, self.settings.dev_mode, mutation_results)
        extinctions += self._reconcile_extinctions(species_list)
        for species in species_list:
            session.add(SpeciesPopulationSnapshot(
                species_id=species.id, generation=species.generation, population=species.population,
                fitness=species.fitness, traits=trait_values(species),
            ))
        session.add(WorldSnapshot(
            world_id=world.id, age_years=world.age_years, tick=next_tick,
            temperature=world.temperature, oxygen=world.oxygen, co2=world.co2, radiation=world.radiation,
        ))
        session.flush()
        logger.info(
            "simulation_step world_id=%s step=%s planet_age_years=%s species=%s mutations=%s extinctions=%s",
            world.id, next_tick, world.age_years, len(species_list), mutations, extinctions,
        )
        return len(species_list), mutations, extinctions

    @staticmethod
    def _reconcile_extinctions(species_list: list[Species]) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        for species in species_list:
            if species.status != SpeciesStatus.EXTINCT and species.population < BALANCE.extinction_threshold:
                species.population = 0
                species.status = SpeciesStatus.EXTINCT
                species.is_player_controlled = False
                species.extinct_at = species.extinct_at or now
                count += 1
        return count

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
