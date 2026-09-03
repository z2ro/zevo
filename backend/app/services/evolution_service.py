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


def active_adaptive_response(session: Session, species_id: int, age_years: int) -> tuple[MutationBias | None, dict[str, float]]:
    row = session.scalar(select(SpeciesEvolution).join(Species).where(
        SpeciesEvolution.species_id == species_id,
        SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS,
        SpeciesEvolution.started_at_year < age_years,
        SpeciesEvolution.complete_at_year >= age_years,
        Species.status == SpeciesStatus.ACTIVE,
        Species.is_player_controlled.is_(True),
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


def cancel_active_adaptive_responses(session: Session, species_id: int) -> None:
    now = datetime.now(timezone.utc)
    for row in session.scalars(select(SpeciesEvolution).where(
        SpeciesEvolution.species_id == species_id,
        SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS,
    )):
        row.status = EvolutionStatus.CANCELLED
        row.completed_at = now


def combine_modifiers(*groups: dict[str, float]) -> dict[str, float]:
    result = {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}
    for group in groups:
        for key in result:
            result[key] *= group.get(key, 1.0)
    return result


def adaptive_response_eligibility(session: Session, species: Species, spec) -> tuple[bool, bool, str | None]:
    minimum = {"LOW": 0.0, "MEDIUM": .25, "HIGH": .5, "CRITICAL": .75}.get(spec.pressure.get("minimum_severity", "LOW"), 0.0)
    available = any(p.type == spec.pressure.get("type") and p.score >= minimum for p in pressures_for_species(session, species))
    active = session.scalar(select(SpeciesEvolution.id).where(
        SpeciesEvolution.species_id == species.id, SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS,
    ))
    completed = {row.evolution_id: row.level for row in session.scalars(select(SpeciesEvolution).where(
        SpeciesEvolution.species_id == species.id, SpeciesEvolution.status == EvolutionStatus.COMPLETED,
    ))}
    reason = (
        "SPECIES_NOT_CONTROLLED" if not species.is_player_controlled or species.status is not SpeciesStatus.ACTIVE
        else "RESPONSE_ACTIVE" if active
        else "PRESSURE_INSUFFICIENT" if not available
        else "INSUFFICIENT_RESOURCES" if any(getattr(species, resource, 0) < cost for resource, cost in spec.cost.items())
        else "REQUIREMENTS_NOT_MET" if any(completed.get(str(req["evolution"]), 0) < int(req["level"]) for req in spec.requirements)
        else None
    )
    return available, reason is None, reason


def start_evolution(session: Session, player_id: int, species_id: int, evolution_id: str, age_years: int) -> SpeciesEvolution:
    species = session.scalar(select(Species).where(Species.id == species_id).with_for_update())
    spec = CONTENT["evolutions"].get(evolution_id)
    if not species or species.creator_id != player_id or not species.is_player_controlled or species.status is not SpeciesStatus.ACTIVE:
        raise EvolutionServiceError("species_not_controlled", "Only the controlled species can evolve")
    if not spec: raise EvolutionServiceError("evolution_not_found", "Evolution does not exist", 404)
    _, can_start, reason = adaptive_response_eligibility(session, species, spec)
    if not can_start:
        errors = {
            "RESPONSE_ACTIVE": ("evolution_active", "An evolution is already in progress"),
            "PRESSURE_INSUFFICIENT": ("response_unavailable", "This adaptive response is not supported by current pressures"),
            "INSUFFICIENT_RESOURCES": ("insufficient_resources", "Not enough resources"),
            "REQUIREMENTS_NOT_MET": ("requirements_not_met", "Evolution requirements are not met"),
        }
        code, message = errors[reason]
        raise EvolutionServiceError(code, message)
    for resource, cost in spec.cost.items(): setattr(species, resource, getattr(species, resource) - cost)
    result = SpeciesEvolution(species_id=species_id, evolution_id=evolution_id, level=int(spec.level or 1), status=EvolutionStatus.IN_PROGRESS,
        started_at_year=age_years, complete_at_year=age_years + int(spec.duration_years))
    session.add(result); session.flush(); return result


def complete_due_evolutions(session: Session, world_id: int, age_years: int) -> list[SpeciesEvolution]:
    rows = list(session.scalars(select(SpeciesEvolution).join(Species).join(Habitat).where(
        Habitat.world_id == world_id, SpeciesEvolution.status == EvolutionStatus.IN_PROGRESS,
        SpeciesEvolution.complete_at_year < age_years).with_for_update()))
    completed = []
    for row in rows:
        species = session.get(Species, row.species_id)
        if not species: continue
        row.status = EvolutionStatus.COMPLETED; row.completed_at = datetime.now(timezone.utc); completed.append(row)
    session.flush(); return completed
