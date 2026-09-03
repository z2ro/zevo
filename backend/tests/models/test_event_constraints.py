import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.bootstrap import bootstrap_world
from app.models import EventRarity, GameEvent, Habitat, Player, Species, SpeciesStatus, SpeciesType, EnergySource, Strategy


def make_event(world_id, code, **overrides):
    values = dict(world_id=world_id, code=code, name=code, description="test",
                  rarity=EventRarity.COMMON, planet_age_years=1, historical=True,
                  global_unique=False, repeat_scope="ALWAYS", event_metadata={})
    values.update(overrides)
    return GameEvent(**values)


def make_species(player_id, habitat_id):
    return Species(name="Scope subject", creator_id=player_id, habitat_id=habitat_id,
                   species_type=SpeciesType.AUTOTROPH, status=SpeciesStatus.ACTIVE,
                   is_player_controlled=True, population=100, generation=0, fitness=1,
                   strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR,
                   thermal_tolerance=10, radiation_tolerance=10, ph_tolerance=10,
                   metabolic_efficiency=10, reproduction_rate=10, mutation_rate=10,
                   energy_efficiency=10, structural_resistance=10)


@pytest.fixture
def subjects(session):
    world = bootstrap_world(session)
    player = session.scalar(select(Player).where(Player.username == "Zero"))
    habitat_id = session.scalar(select(Habitat.id).where(Habitat.world_id == world.id))
    species = make_species(player.id, habitat_id)
    session.add(species); session.commit()
    return world, player, species


@pytest.mark.parametrize("scope,subject", [("WORLD", None), ("SPECIES", "species"), ("PLAYER", "player")])
def test_once_scope_rejects_duplicate(session, subjects, scope, subject):
    world, player, species = subjects
    kwargs = {"repeat_scope": scope}
    if subject == "species": kwargs["species_id"] = species.id
    if subject == "player": kwargs["player_id"] = player.id
    session.add(make_event(world.id, f"ONCE_{scope}", **kwargs)); session.commit()
    session.add(make_event(world.id, f"ONCE_{scope}", **kwargs))
    with pytest.raises(IntegrityError):
        session.commit()


def test_idempotency_key_rejects_duplicate(session, subjects):
    world, _, _ = subjects
    session.add(make_event(world.id, "REPEATABLE", idempotency_key="tick:7:event")); session.commit()
    session.add(make_event(world.id, "REPEATABLE", idempotency_key="tick:7:event"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_code_with_distinct_keys_is_allowed(session, subjects):
    world, _, _ = subjects
    session.add_all([make_event(world.id, "REPEATABLE", idempotency_key="tick:1"), make_event(world.id, "REPEATABLE", idempotency_key="tick:2")])
    session.commit()
    assert session.query(GameEvent).filter_by(code="REPEATABLE").count() == 2


@pytest.mark.parametrize("scope", ["SPECIES", "PLAYER"])
def test_subject_scope_requires_subject(session, subjects, scope):
    world, _, _ = subjects
    session.add(make_event(world.id, f"MISSING_{scope}", repeat_scope=scope))
    with pytest.raises(IntegrityError):
        session.commit()


def test_repeat_scope_rejects_unknown_value(session, subjects):
    world, _, _ = subjects
    session.add(make_event(world.id, "BAD_SCOPE", repeat_scope="GALAXY"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_event_constraints_compile_for_postgresql():
    dialect = postgresql.dialect()
    table_ddl = str(CreateTable(GameEvent.__table__).compile(dialect=dialect))
    index_ddl = "\n".join(str(CreateIndex(index).compile(dialect=dialect)) for index in GameEvent.__table__.indexes)
    assert "repeat_scope IN ('ALWAYS', 'WORLD', 'SPECIES', 'PLAYER')" in table_ddl
    assert "WHERE idempotency_key IS NOT NULL" in index_ddl
    assert "WHERE repeat_scope = 'SPECIES'" in index_ddl
    assert "WHERE repeat_scope = 'PLAYER'" in index_ddl
