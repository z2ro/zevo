from __future__ import annotations

from threading import Lock

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.game_balance import BOT_USERNAMES, HABITATS_INITIAL, WORLD_INITIAL
from app.models import Habitat, Player, World


_bootstrap_lock = Lock()


def _lock_bootstrap(session: Session) -> None:
    """Serialize initial data creation across processes on PostgreSQL."""
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(20260902)"))


def bootstrap_world(session: Session) -> World:
    """Create the canonical world, habitats and players; safe to call repeatedly."""
    with _bootstrap_lock:
        try:
            _lock_bootstrap(session)
            world = session.scalar(select(World).where(World.name == WORLD_INITIAL["name"]))
            if world is None:
                world = World(**WORLD_INITIAL)
                session.add(world)
                session.flush()

            existing_habitats = set(session.scalars(select(Habitat.name).where(Habitat.world_id == world.id)))
            for values in HABITATS_INITIAL:
                name, temperature, radiation, ph, water, solar, chemical, organic, capacity = values
                if name not in existing_habitats:
                    session.add(Habitat(world_id=world.id, name=name, temperature=temperature, radiation=radiation, ph=ph, water=water, solar_energy=solar, chemical_energy=chemical, organic_resources=organic, carrying_capacity=capacity))

            players = {"Zero": (False, None), **{name: (True, name.removesuffix("Bot").upper()) for name in BOT_USERNAMES}}
            existing_players = set(session.scalars(select(Player.username).where(Player.username.in_(players))))
            for username, (is_bot, kind) in players.items():
                if username not in existing_players:
                    session.add(Player(username=username, is_bot=is_bot, bot_kind=kind))
            session.commit()
        except IntegrityError:
            # A non-PostgreSQL process or an initializer predating the advisory
            # lock may win the race. Recover by reading the canonical row.
            session.rollback()
            world = session.scalar(select(World).where(World.name == WORLD_INITIAL["name"]))
            if world is None:
                raise
        session.refresh(world)
        return world
