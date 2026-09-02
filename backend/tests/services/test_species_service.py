from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.db.base import Base
from app.db.session import create_engine_for_url
from app.models import Habitat, Player, SpeciesStatus, World
from app.schemas.species import SpeciesCreate
from app.services.species_service import (
    SpeciesServiceError,
    abandon_species,
    create_species,
    preview_species,
)


@pytest.fixture
def session():
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        world = World(name="Eos-1", generation=0, tick=0, temperature=60, oxygen=1,
                      co2=70, radiation=50, water_availability=70, average_ph=6,
                      solar_energy=60, chemical_energy=70, geological_activity=80)
        value.add(world); value.flush()
        value.add(Habitat(world_id=world.id, name="Ocean", temperature=50, radiation=40,
                          ph=6, water=90, solar_energy=70, chemical_energy=50,
                          organic_resources=50, carrying_capacity=10000))
        value.add_all([Player(username="Zero"), Player(username="Other")])
        value.commit()
        yield value
    engine.dispose()


def payload(**changes):
    data = {
        "name": "Proto Zero",
        "species_type": "AUTOTROPH",
        "energy_source": "SOLAR",
        "strategy": "COLONIZER",
        "habitat_id": 1,
        "traits": {
            "thermal_tolerance": 20, "radiation_tolerance": 10,
            "ph_tolerance": 10, "metabolic_efficiency": 15,
            "reproduction_rate": 15, "mutation_rate": 5,
            "energy_efficiency": 15, "structural_resistance": 10,
        },
    }
    data.update(changes)
    return data


def test_budget_maximum_is_accepted_and_excess_is_rejected():
    assert SpeciesCreate.model_validate(payload()).traits.cost == 100
    excessive = payload()
    excessive["traits"] = {**excessive["traits"], "mutation_rate": 6}
    with pytest.raises(ValidationError, match="trait budget exceeded"):
        SpeciesCreate.model_validate(excessive)


@pytest.mark.parametrize("changes", [
    {"species_type": "PARASITIC", "energy_source": "ORGANIC", "strategy": "PARASITE"},
    {"species_type": "AUTOTROPH", "energy_source": "PARASITIC", "strategy": "PARASITE"},
])
def test_invalid_parasite_combinations_are_rejected(changes):
    with pytest.raises(ValidationError, match="must be used together"):
        SpeciesCreate.model_validate(payload(**changes))


def test_preview_reuses_public_simulation_shape(session):
    result = preview_species(session, SpeciesCreate.model_validate(payload()))
    assert result.estimated_fitness > 0
    assert result.estimated_growth in {"positive", "stable", "negative"}
    assert result.risk in {"low", "moderate", "high"}
    assert 0 <= result.environment_compatibility <= 1


def test_create_sets_canonical_initial_state_and_prevents_second_controlled(session):
    data = SpeciesCreate.model_validate(payload())
    created = create_species(session, 1, data)
    session.commit()
    assert created.population == 100
    assert created.status is SpeciesStatus.ACTIVE
    assert created.is_player_controlled is True
    assert created.fitness == preview_species(session, data).estimated_fitness

    with pytest.raises(SpeciesServiceError) as error:
        create_species(session, 1, SpeciesCreate.model_validate(payload(name="Second")))
    assert (error.value.status_code, error.value.code) == (409, "controlled_species_exists")
    assert error.value.as_error()["error"]["details"]["species_id"] == created.id


def test_abandon_preserves_species_as_wild_and_allows_new_species(session):
    first = create_species(session, 1, SpeciesCreate.model_validate(payload()))
    session.commit()
    abandoned = abandon_species(session, 1, first.id)
    session.commit()
    assert abandoned.status is SpeciesStatus.WILD
    assert abandoned.is_player_controlled is False
    assert abandoned.abandoned_at is not None
    assert abandoned.creator_id == 1

    second = create_species(session, 1, SpeciesCreate.model_validate(payload(name="Successor")))
    session.commit()
    assert second.id != first.id and second.is_player_controlled


def test_cannot_abandon_another_players_species(session):
    species = create_species(session, 1, SpeciesCreate.model_validate(payload()))
    session.commit()
    with pytest.raises(SpeciesServiceError) as error:
        abandon_species(session, 2, species.id)
    assert (error.value.status_code, error.value.code) == (409, "species_not_controlled")


def test_missing_habitat_and_player_are_api_friendly(session):
    with pytest.raises(SpeciesServiceError) as habitat_error:
        preview_species(session, SpeciesCreate.model_validate(payload(habitat_id=99)))
    assert habitat_error.value.as_error()["error"]["code"] == "habitat_not_found"

    with pytest.raises(SpeciesServiceError) as player_error:
        create_species(session, 99, SpeciesCreate.model_validate(payload()))
    assert player_error.value.status_code == 404
