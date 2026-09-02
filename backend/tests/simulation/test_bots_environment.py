from random import Random
from sqlalchemy import func, select
from app.config.game_balance import BALANCE
from app.db.bootstrap import bootstrap_world
from app.models.entities import Player, Species
from app.simulation.bots import run_bots


def test_all_bots_create_one_valid_species(session):
    world = bootstrap_world(session)
    world.tick = BALANCE.bot_action_interval_ticks
    assert run_bots(session, world, Random(1)) == 5
    assert session.scalar(select(func.count()).select_from(Species)) == 5
    assert all(session.scalar(select(func.count()).select_from(Species).where(
        Species.creator_id == player.id, Species.is_player_controlled.is_(True))) == 1
        for player in session.scalars(select(Player).where(Player.is_bot.is_(True))))
