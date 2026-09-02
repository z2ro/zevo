from __future__ import annotations

import random
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE, BalanceConfig
from app.models.entities import SpeciesRelation
from app.models.enums import RelationType

from .common import clamp, enum_value
from .fitness import FitnessContext


@dataclass(frozen=True)
class CompetitionResult:
    pressure: float
    competitors: tuple[int, ...]


@dataclass(frozen=True)
class HostCompatibilityResult:
    compatible: bool
    score: float


@dataclass(frozen=True)
class ParasitismResult:
    parasite_id: int | None
    host_id: int | None
    compatibility: float
    established: bool
    strength: float
    infection_rate: float
    virulence: float
    transmission_rate: float


def _alive(species: object) -> bool:
    return enum_value(getattr(species, "status")) != "EXTINCT" and getattr(species, "population", 0) > 0


def _same_habitat(left: object, right: object) -> bool:
    return getattr(left, "habitat_id", None) == getattr(right, "habitat_id", None)


def _resource_profile(species: object, balance: BalanceConfig = BALANCE) -> tuple[float, float, float]:
    """Return use of solar, chemical and organic resource pools."""
    source = enum_value(getattr(species, "energy_source"))
    return balance.resource_profiles.get(source, (0.0, 0.0, 0.0))


def resource_overlap(left: object, right: object, balance: BalanceConfig = BALANCE) -> float:
    """Cosine similarity between ecological resource profiles, in ``[0, 1]``."""
    a, b = _resource_profile(left, balance), _resource_profile(right, balance)
    denominator = sqrt(sum(value * value for value in a)) * sqrt(sum(value * value for value in b))
    if denominator == 0:
        return 0.0
    return round(clamp(sum(x * y for x, y in zip(a, b)) / denominator, 0.0, 1.0), 6)


def competition_pressure(
    focal: object,
    species_in_habitat: Iterable[object],
    carrying_capacity: int,
    balance: BalanceConfig = BALANCE,
) -> CompetitionResult:
    """Aggregate population x metabolism x overlap into bounded pressure."""
    if carrying_capacity <= 0 or not _alive(focal):
        return CompetitionResult(0.0, ())

    focal_id = getattr(focal, "id", None)
    weighted_population = 0.0
    competitors: list[int] = []
    for other in species_in_habitat:
        if other is focal or (focal_id is not None and getattr(other, "id", None) == focal_id):
            continue
        if not _alive(other) or not _same_habitat(focal, other):
            continue
        overlap = resource_overlap(focal, other, balance)
        if overlap <= 0:
            continue
        metabolism = clamp(getattr(other, "metabolic_efficiency", 0) / 100.0, 0.0, 1.0)
        weighted_population += getattr(other, "population", 0) * metabolism * overlap
        other_id = getattr(other, "id", None)
        if other_id is not None:
            competitors.append(other_id)

    pressure = clamp(weighted_population / carrying_capacity, 0.0, 1.0)
    return CompetitionResult(round(pressure, 6), tuple(sorted(competitors)))


def host_compatibility(
    parasite: object,
    host: object,
    *,
    previous_contact: float = 0.0,
    balance: BalanceConfig = BALANCE,
) -> HostCompatibilityResult:
    """Score a potential host without randomness; establishment owns the RNG roll."""
    valid = (
        _alive(parasite)
        and _alive(host)
        and enum_value(getattr(parasite, "species_type")) == "PARASITIC"
        and enum_value(getattr(host, "species_type")) != "PARASITIC"
        and getattr(parasite, "id", None) != getattr(host, "id", None)
        and _same_habitat(parasite, host)
    )
    if not valid:
        return HostCompatibilityResult(False, 0.0)

    # Contact rises with host abundance. Resistance and trait divergence constrain
    # infection, while mutation and historical contact broaden compatibility.
    contact = clamp(getattr(host, "population", 0) / balance.host_abundance_scale, 0.0, 1.0)
    vulnerability = 1.0 - clamp(getattr(host, "structural_resistance", 0) / 100.0, 0.0, 1.0)
    trait_similarity = 1.0 - abs(
        getattr(parasite, "thermal_tolerance", 0) - getattr(host, "thermal_tolerance", 0)
    ) / 100.0
    adaptability = clamp(getattr(parasite, "mutation_rate", 0) / 100.0, 0.0, 1.0)
    weights = balance.host_compatibility_weights
    score = sum(weight * value for weight, value in zip(weights, (
        contact, vulnerability, trait_similarity, adaptability, clamp(previous_contact, 0.0, 1.0)
    )))
    score = round(clamp(score, 0.0, 1.0), 6)
    return HostCompatibilityResult(score >= balance.host_compatibility_threshold, score)


def evaluate_parasitism(
    parasite: object,
    host: object,
    rng: random.Random,
    *,
    previous_contact: float = 0.0,
    balance: BalanceConfig = BALANCE,
) -> ParasitismResult:
    """Evaluate relation establishment using only the injected deterministic RNG."""
    compatibility = host_compatibility(parasite, host, previous_contact=previous_contact, balance=balance)
    transmission = compatibility.score * clamp(
        (getattr(parasite, "energy_efficiency", 0) + getattr(parasite, "reproduction_rate", 0)) / balance.parasite_trait_scale,
        0.0,
        1.0,
    )
    infection = compatibility.score * transmission
    virulence = clamp(
        (getattr(parasite, "metabolic_efficiency", 0) + getattr(parasite, "mutation_rate", 0)) / balance.parasite_trait_scale,
        0.0,
        1.0,
    )
    established = compatibility.compatible and rng.random() < transmission
    strength = compatibility.score * sum(w * v for w, v in zip(balance.parasite_strength_weights, (transmission, virulence))) if established else 0.0
    return ParasitismResult(
        getattr(parasite, "id", None),
        getattr(host, "id", None),
        compatibility.score,
        established,
        round(strength, 6),
        round(infection, 6),
        round(virulence, 6),
        round(transmission, 6),
    )


def fitness_context_for(
    focal: object,
    living_species: Iterable[object],
    carrying_capacity: int,
    balance: BalanceConfig = BALANCE,
) -> FitnessContext:
    """Integration hook consumed by the simulation fitness calculation."""
    candidates = tuple(living_species)
    competition = competition_pressure(focal, candidates, carrying_capacity, balance).pressure
    host_score = 0.0
    if enum_value(getattr(focal, "species_type")) == "PARASITIC":
        host_score = max((host_compatibility(focal, candidate, balance=balance).score for candidate in candidates), default=0.0)
    return FitnessContext(competition=competition, host_compatibility=host_score)


def persist_parasitism_relation(
    session: Session,
    result: ParasitismResult,
) -> SpeciesRelation | None:
    """Create or refresh an established relation; transaction ownership stays external."""
    if not result.established or result.parasite_id is None or result.host_id is None:
        return None
    relation = session.scalar(
        select(SpeciesRelation).where(
            SpeciesRelation.predator_or_parasite_id == result.parasite_id,
            SpeciesRelation.target_species_id == result.host_id,
            SpeciesRelation.relation_type == RelationType.PARASITISM,
        )
    )
    if relation is None:
        relation = SpeciesRelation(
            predator_or_parasite_id=result.parasite_id,
            target_species_id=result.host_id,
            relation_type=RelationType.PARASITISM,
            strength=result.strength,
            infection_rate=result.infection_rate,
            virulence=result.virulence,
            transmission_rate=result.transmission_rate,
        )
        session.add(relation)
    else:
        relation.strength = result.strength
        relation.infection_rate = result.infection_rate
        relation.virulence = result.virulence
        relation.transmission_rate = result.transmission_rate
    return relation
