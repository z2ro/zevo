from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine import CONTENT
from app.models.entities import Habitat, Species, SpeciesEvolution
from app.models.enums import EvolutionStatus, SpeciesStatus
from app.simulation.pressures import resolve_pressures
from app.simulation.evolution import MutationBias
from app.simulation.interactions import fitness_context_for


class EvolutionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code, self.message, self.status_code = code, message, status_code


def pressures_for_species(session: Session, species: Species):
    habitat = session.get(Habitat, species.habitat_id)
    living = list(session.scalars(select(Species).where(
        Species.habitat_id == species.habitat_id, Species.status != SpeciesStatus.EXTINCT,
    )))
    context = fitness_context_for(species, living, habitat.carrying_capacity) if habitat else None
    return resolve_pressures(species, habitat, context) if habitat and context else []


def active_adaptive_response(session: Session, species_id: int, tick: int) -> tuple[MutationBias | None, dict[str, float]]:
    row = session.scalar(select(SpeciesEvolution).where(
        SpeciesEvolution.species_id == species_id,
        SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS,
        SpeciesEvolution.started_at_tick < tick,
        SpeciesEvolution.complete_at_tick >= tick,
    ).order_by(SpeciesEvolution.id.desc()))
    if not row:
        return None, {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}
    spec = CONTENT["evolutions"].get(row.evolution_id)
    if not spec:
        return None, {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}
    bias = MutationBias(str(spec.selection_bias["trait"]), float(spec.selection_bias["strength"]))
    modifiers = {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}
    modifiers.update(spec.tradeoffs)
    return bias, modifiers


def combine_modifiers(*groups: dict[str, float]) -> dict[str, float]:
    return {key: groups[0].get(key, 1.0) * groups[1].get(key, 1.0) for key in ("reproduction_modifier", "mortality_modifier")}


def start_evolution(session: Session, player_id: int, species_id: int, evolution_id: str, tick: int) -> SpeciesEvolution:
    species = session.scalar(select(Species).where(Species.id == species_id).with_for_update())
    spec = CONTENT["evolutions"].get(evolution_id)
    if not species or species.creator_id != player_id or not species.is_player_controlled or species.status is not SpeciesStatus.ACTIVE:
        raise EvolutionServiceError("species_not_controlled", "Only the controlled species can evolve")
    if not spec: raise EvolutionServiceError("evolution_not_found", "Evolution does not exist", 404)
    if spec.pressure:
        pressure_type = spec.pressure.get("type")
        minimum = {"LOW": 0.0, "MEDIUM": .25, "HIGH": .5, "CRITICAL": .75}.get(spec.pressure.get("minimum_severity", "LOW"), 0.0)
        if not any(p.type == pressure_type and p.score >= minimum for p in pressures_for_species(session, species)):
            raise EvolutionServiceError("response_unavailable", "This adaptive response is not supported by current pressures")
    active = session.scalar(select(SpeciesEvolution.id).where(SpeciesEvolution.species_id == species_id, SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS))
    if active: raise EvolutionServiceError("evolution_active", "An evolution is already in progress")
    completed = {row.evolution_id: row.level for row in session.scalars(select(SpeciesEvolution).where(SpeciesEvolution.species_id == species_id, SpeciesEvolution.status == EvolutionStatus.COMPLETED))}
    for requirement in spec.requirements:
        if completed.get(str(requirement["evolution"]), 0) < int(requirement["level"]):
            raise EvolutionServiceError("requirements_not_met", "Evolution requirements are not met")
    for resource, cost in spec.cost.items():
        if getattr(species, resource, 0) < cost: raise EvolutionServiceError("insufficient_resources", "Not enough resources")
    for resource, cost in spec.cost.items(): setattr(species, resource, getattr(species, resource) - cost)
    result = SpeciesEvolution(species_id=species_id, evolution_id=evolution_id, level=int(spec.level or 1), status=EvolutionStatus.IN_PROGRESS,
        started_at_tick=tick, complete_at_tick=tick + int(spec.duration_ticks))
    session.add(result); session.flush(); return result


def complete_due_evolutions(session: Session, world_id: int, tick: int) -> list[SpeciesEvolution]:
    rows = list(session.scalars(select(SpeciesEvolution).join(Species).join(Habitat).where(
        Habitat.world_id == world_id, SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS,
        SpeciesEvolution.complete_at_tick <= tick).with_for_update()))
    completed = []
    for row in rows:
        species = session.get(Species, row.species_id)
        if not species: continue
        row.status = EvolutionStatus.COMPLETED; row.completed_at = datetime.now(timezone.utc); completed.append(row)
    session.flush(); return completed
