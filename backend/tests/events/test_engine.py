from __future__ import annotations

import sys
from pathlib import Path
from random import Random

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.db.base import Base
from app.db.session import create_engine_for_url
from app.events.conditions import All, Any, FieldCondition, Not, Predicate, RandomRoll
from app.events.core import CallbackConsequence, EventContext, EventDefinition, EventEvaluator, RepeatPolicy
from app.events.service import EventService
from app.models.entities import GameEvent, Habitat, HistoricalFlag, Player, Species, World
from app.models.enums import EnergySource, EventRarity, SpeciesStatus, SpeciesType, Strategy


@pytest.fixture
def session():
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
    engine.dispose()


@pytest.fixture
def context(session):
    world = World(
        name="Test", generation=12000, tick=12, temperature=50, oxygen=1, co2=70,
        radiation=50, water_availability=60, average_ph=5, solar_energy=40,
        chemical_energy=70, geological_activity=80,
    )
    player = Player(username="Zero", is_bot=False)
    session.add_all([world, player]); session.flush()
    habitat = Habitat(
        world_id=world.id, name="Ocean", temperature=50, radiation=20, ph=6,
        water=90, solar_energy=50, chemical_energy=50, organic_resources=50,
        carrying_capacity=1000,
    )
    session.add(habitat); session.flush()
    species = Species(
        name="Alpha", creator_id=player.id, habitat_id=habitat.id,
        species_type=SpeciesType.AUTOTROPH, status=SpeciesStatus.ACTIVE,
        is_player_controlled=True, population=200, generation=12000, fitness=1.2,
        strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR,
        thermal_tolerance=12, radiation_tolerance=12, ph_tolerance=12,
        metabolic_efficiency=12, reproduction_rate=12, mutation_rate=12,
        energy_efficiency=12, structural_resistance=12,
    )
    session.add(species); session.flush()
    return EventContext(
        world=world, species=species, player=player, rng=Random(7),
        values={"interaction": {"strength": 0.8}},
    )


def definition(condition, **overrides):
    values = dict(
        code="TEST_EVENT", name="Test event", description="Test",
        rarity=EventRarity.COMMON, condition=condition,
    )
    values.update(overrides)
    return EventDefinition(**values)


def test_composable_conditions_and_dotted_values(context):
    condition = All((
        FieldCondition("species.population", "gt", 100),
        Any((
            FieldCondition("world.oxygen", "gt", 50),
            FieldCondition("interaction.strength", "ge", 0.8),
        )),
        Not(FieldCondition("species.status", "eq", SpeciesStatus.EXTINCT)),
    ))
    assert EventEvaluator().evaluate(definition(condition), context).matched
    assert not FieldCondition("missing.value", "eq", 1).evaluate(context)


def test_random_roll_is_seeded_and_dev_multiplier_is_bounded(context):
    context.rng = Random(1)
    assert RandomRoll(0.14).evaluate(context)  # first random is ~0.134
    context.rng = Random(1)
    context.dev_mode = True
    assert RandomRoll(0.01, dev_multiplier=20).evaluate(context)
    with pytest.raises(ValueError):
        RandomRoll(1.1).evaluate(context)


def test_unmatched_definition_is_not_persisted(session, context):
    result = EventService(session).evaluate_and_persist(
        definition(Predicate("never", lambda _: False)), context
    )
    assert not result.matched
    assert session.scalar(select(func.count()).select_from(GameEvent)) == 0


def test_persists_metadata_and_consequence_atomically(session, context):
    def reduce_population(ctx):
        ctx.species.population -= 10
        return {"population_delta": -10}

    event_definition = definition(
        Predicate("always", lambda _: True),
        metadata_factory=lambda ctx: {"species_name": ctx.species.name},
        consequences=(CallbackConsequence("reduce_population", reduce_population),),
    )
    result = EventService(session).evaluate_and_persist(event_definition, context)
    event = session.get(GameEvent, result.event_id)
    assert result.persisted and result.effects == ({"population_delta": -10},)
    assert event.event_metadata["species_name"] == "Alpha"
    assert context.species.population == 190


def test_failed_consequence_does_not_leave_event(session, context):
    def fail(_):
        raise RuntimeError("effect failed")

    with pytest.raises(RuntimeError):
        EventService(session).evaluate_and_persist(
            definition(
                Predicate("always", lambda _: True),
                consequences=(CallbackConsequence("fail", fail),),
            ),
            context,
        )
    assert session.scalar(select(func.count()).select_from(GameEvent)) == 0


def test_idempotency_key_prevents_duplicate_repeatable_event(session, context):
    service = EventService(session)
    item = definition(Predicate("always", lambda _: True))
    first = service.evaluate_and_persist(item, context, idempotency_key="tick:12:test")
    second = service.evaluate_and_persist(item, context, idempotency_key="tick:12:test")
    assert first.persisted
    assert not second.persisted and second.reason == "duplicate"
    assert first.event_id == second.event_id


@pytest.mark.parametrize(
    "policy", [RepeatPolicy.ONCE_PER_WORLD, RepeatPolicy.ONCE_PER_SPECIES, RepeatPolicy.ONCE_PER_PLAYER]
)
def test_repeat_policies(session, context, policy):
    service = EventService(session)
    item = definition(Predicate("always", lambda _: True), repeat_policy=policy)
    assert service.evaluate_and_persist(item, context).persisted
    assert service.evaluate_and_persist(item, context).reason == "duplicate"


def test_global_unique_is_persisted_once(session, context):
    item = definition(
        Predicate("always", lambda _: True),
        rarity=EventRarity.WORLD_FIRST,
        global_unique=True,
        repeat_policy=RepeatPolicy.ONCE_PER_WORLD,
    )
    service = EventService(session)
    assert service.evaluate_and_persist(item, context).persisted
    assert service.evaluate_and_persist(item, context).reason == "duplicate"


def test_historical_flags_are_idempotent_by_subject(session, context):
    service = EventService(session)
    first = service.ensure_flag(
        context, "SURVIVED", species_id=context.species.id, metadata={"source": "test"}
    )
    second = service.ensure_flag(context, "SURVIVED", species_id=context.species.id)
    assert first.id == second.id
    assert first.flag_metadata == {"source": "test"}
    assert session.scalar(select(func.count()).select_from(HistoricalFlag)) == 1


def test_subject_policy_requires_subject(session, context):
    context.species = None
    item = definition(
        Predicate("always", lambda _: True), repeat_policy=RepeatPolicy.ONCE_PER_SPECIES
    )
    with pytest.raises(ValueError, match="context.species"):
        EventService(session).evaluate_and_persist(item, context)
