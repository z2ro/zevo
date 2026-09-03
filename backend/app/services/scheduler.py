from __future__ import annotations

import logging
from threading import Event, Thread

from sqlalchemy import select
from app.config.settings import get_settings
from app.db.session import get_session_factory
from app.models.entities import World
from app.services.simulation_service import SimulationService

logger = logging.getLogger(__name__)


def start_scheduler() -> tuple[Event, Thread]:
    stop = Event()

    def loop() -> None:
        settings = get_settings()
        while not stop.wait(settings.simulation_interval_seconds):
            with get_session_factory()() as session:
                try:
                    for world_id in session.scalars(select(World.id)):
                        SimulationService(settings).run_tick(session, world_id)
                    session.commit()
                except Exception:
                    session.rollback(); logger.exception("simulation_tick_failed")

    thread = Thread(target=loop, name="zevo-simulation", daemon=True)
    thread.start()
    return stop, thread
