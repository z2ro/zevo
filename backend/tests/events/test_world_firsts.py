from random import Random
from sqlalchemy import func, select
from app.config.game_balance import BALANCE
from app.events.definitions import evaluate_tick_events
from app.models.entities import GameEvent, Species, World
from backend.tests.simulation.test_service import build_world
from backend.tests.simulation.conftest import session  # noqa: F401


def test_world_first_is_once_per_world(session):
    world_id, species_id, _ = build_world(session)
    world, species = session.get(World, world_id), session.get(Species, species_id)
    species.generation = BALANCE.stable_life_generations
    evaluate_tick_events(session, world, [species], Random(1), False, {})
    evaluate_tick_events(session, world, [species], Random(1), False, {})
    assert session.scalar(select(func.count()).select_from(GameEvent).where(
        GameEvent.code == "FIRST_STABLE_LIFE")) == 1
