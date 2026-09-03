from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine import CONTENT
from app.engine.effects import EffectExecutionContext, execute_effects
from app.models.entities import Habitat, Species, SpeciesEvolution
from app.models.enums import EvolutionStatus, SpeciesStatus
from app.simulation.pressures import resolve_pressures
from app.simulation.fitness import FitnessContext


class EvolutionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code, self.message, self.status_code = code, message, status_code


def start_evolution(session: Session, player_id: int, species_id: int, evolution_id: str, tick: int) -> SpeciesEvolution:
    species = session.scalar(select(Species).where(Species.id == species_id).with_for_update())
    spec = CONTENT["evolutions"].get(evolution_id)
    if not species or species.creator_id != player_id or not species.is_player_controlled or species.status is not SpeciesStatus.ACTIVE:
        raise EvolutionServiceError("species_not_controlled", "Only the controlled species can evolve")
    if not spec: raise EvolutionServiceError("evolution_not_found", "Evolution does not exist", 404)
    if spec.pressure:
        pressure_type = spec.pressure.get("type")
        minimum = {"LOW": 0.0, "MEDIUM": .25, "HIGH": .5, "CRITICAL": .75}.get(spec.pressure.get("minimum_severity", "LOW"), 0.0)
        habitat = session.get(Habitat, species.habitat_id)
        if not habitat or not any(p.type == pressure_type and p.score >= minimum for p in resolve_pressures(species, habitat)):
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
    rows = list(session.scalars(select(SpeciesEvolution).join(Species).where(SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS,
        SpeciesEvolution.complete_at_tick <= tick, Species.habitat_id.is_not(None)).with_for_update()))
    completed = []
    for row in rows:
        species = session.get(Species, row.species_id); spec = CONTENT["evolutions"].get(row.evolution_id)
        if not species or not spec: continue
        execute_effects(spec.effects, EffectExecutionContext(world=None, species=species))
        row.status = EvolutionStatus.COMPLETED; row.completed_at = datetime.now(timezone.utc); completed.append(row)
    session.flush(); return completed
