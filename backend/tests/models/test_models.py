from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.db.bootstrap import bootstrap_world
from app.models import HistoricalFlag, Player, Species, SpeciesStatus, SpeciesType, EnergySource, Strategy


def species_kwargs(player_id: int, habitat_id: int, **overrides):
    values = dict(name="Simplex", creator_id=player_id, habitat_id=habitat_id,
                  species_type=SpeciesType.AUTOTROPH, status=SpeciesStatus.ACTIVE,
                  is_player_controlled=True, population=100, generation=0,
                  fitness=1.0, strategy=Strategy.COLONIZER,
                  energy_source=EnergySource.SOLAR, thermal_tolerance=15,
                  radiation_tolerance=15, ph_tolerance=15,
                  metabolic_efficiency=15, reproduction_rate=10,
                  mutation_rate=5, energy_efficiency=15,
                  structural_resistance=10)
    values.update(overrides)
    return values


def test_bootstrap_is_idempotent(session):
    first = bootstrap_world(session)
    second = bootstrap_world(session)
    assert first.id == second.id
    assert session.query(Player).count() == 6
    assert len(first.name) > 0


def test_postgresql_boolean_constraints_are_portable():
    ddl = str(CreateTable(Species.__table__).compile(dialect=postgresql.dialect()))
    assert "is_player_controlled IS FALSE" in ddl
    assert "is_player_controlled = 0" not in ddl


def test_only_one_controlled_species_per_player(session):
    world = bootstrap_world(session)
    player = session.scalar(select(Player).where(Player.username == "Zero"))
    habitat_id = session.execute(select(Species.__table__.c.habitat_id)).scalar_one_or_none()
    if habitat_id is None:
        from app.models import Habitat
        habitat_id = session.scalar(select(Habitat.id).where(Habitat.world_id == world.id))
    session.add(Species(**species_kwargs(player.id, habitat_id)))
    session.commit()
    session.add(Species(**species_kwargs(player.id, habitat_id, name="Duplex")))
    with pytest.raises(IntegrityError):
        session.commit()


def test_global_historical_flag_is_unique(session):
    world = bootstrap_world(session)
    session.add(HistoricalFlag(world_id=world.id, code="FIRST_STABLE_LIFE", generation=1000))
    session.commit()
    session.add(HistoricalFlag(world_id=world.id, code="FIRST_STABLE_LIFE", generation=2000))
    with pytest.raises(IntegrityError):
        session.commit()


def test_initial_migration_is_frozen():
    source = (Path(__file__).resolve().parents[2] / "alembic/versions/0001_initial_schema.py").read_text()
    assert "op.create_table" in source
    assert "Base.metadata" not in source
    assert "create_all" not in source
