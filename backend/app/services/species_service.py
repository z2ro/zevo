from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE
from app.models import Habitat, Player, Species
from app.models.enums import SpeciesStatus
from app.schemas.species import SpeciesCreate, SpeciesPreview
from app.simulation.fitness import FitnessContext, preview_fitness
from app.simulation.interactions import host_compatibility


@dataclass(frozen=True)
class SpeciesServiceError(Exception):
    code: str
    message: str
    status_code: int
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        return self.message

    def as_error(self) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details or {},
            }
        }


def _habitat(session: Session, habitat_id: int) -> Habitat:
    habitat = session.get(Habitat, habitat_id)
    if habitat is None:
        raise SpeciesServiceError(
            "habitat_not_found", "Habitat does not exist", 404, {"habitat_id": habitat_id}
        )
    return habitat


def _candidate(data: SpeciesCreate, creator_id: int = 0) -> Species:
    return Species(
        name=data.name,
        creator_id=creator_id,
        habitat_id=data.habitat_id,
        species_type=data.species_type,
        status=SpeciesStatus.ACTIVE,
        is_player_controlled=True,
        population=BALANCE.initial_population,
        generation=0,
        fitness=1.0,
        strategy=data.strategy,
        energy_source=data.energy_source,
        **data.traits.model_dump(),
    )


def preview_species(session: Session, data: SpeciesCreate) -> SpeciesPreview:
    habitat = _habitat(session, data.habitat_id)
    candidate = _candidate(data)
    context = FitnessContext()
    if data.species_type.value == "PARASITIC":
        hosts = session.scalars(select(Species).where(
            Species.habitat_id == habitat.id, Species.status != SpeciesStatus.EXTINCT,
            Species.population > 0,
        ))
        context = FitnessContext(host_compatibility=max(
            (host_compatibility(candidate, host).score for host in hosts), default=0.0
        ))
    return SpeciesPreview.model_validate(preview_fitness(candidate, habitat, context))


def create_species(session: Session, player_id: int, data: SpeciesCreate) -> Species:
    # Locking the player serializes creations on PostgreSQL. The database partial
    # unique index remains the final guard against races and covers SQLite tests.
    player = session.scalar(select(Player).where(Player.id == player_id).with_for_update())
    if player is None:
        raise SpeciesServiceError(
            "player_not_found", "Player does not exist", 404, {"player_id": player_id}
        )
    habitat = _habitat(session, data.habitat_id)
    controlled = session.scalar(
        select(Species.id).where(
            Species.creator_id == player_id,
            Species.is_player_controlled.is_(True),
        )
    )
    if controlled is not None:
        raise SpeciesServiceError(
            "controlled_species_exists",
            "Player already controls a species",
            409,
            {"species_id": controlled},
        )

    species = _candidate(data, player_id)
    species.fitness = float(preview_fitness(species, habitat)["estimated_fitness"])
    session.add(species)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SpeciesServiceError(
            "controlled_species_exists", "Player already controls a species", 409
        ) from exc
    return species


def abandon_species(session: Session, player_id: int, species_id: int) -> Species:
    species = session.scalar(
        select(Species).where(Species.id == species_id).with_for_update()
    )
    if species is None:
        raise SpeciesServiceError(
            "species_not_found", "Species does not exist", 404, {"species_id": species_id}
        )
    if species.creator_id != player_id or not species.is_player_controlled:
        raise SpeciesServiceError(
            "species_not_controlled", "Only the player's current species can be abandoned", 409
        )
    if species.status is not SpeciesStatus.ACTIVE:
        raise SpeciesServiceError(
            "invalid_species_status", "Only an ACTIVE species can be abandoned", 409
        )

    species.status = SpeciesStatus.WILD
    species.is_player_controlled = False
    species.abandoned_at = datetime.now(timezone.utc)
    session.flush()
    return species
