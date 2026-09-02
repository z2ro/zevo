from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql+psycopg://zevo:zevo@postgres:5432/zevo"
    simulation_tick_seconds: float = 5.0
    generations_per_tick: int = 1000
    simulation_random_seed: int | None = None
    dev_mode: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        seed = os.getenv("SIMULATION_RANDOM_SEED")
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            simulation_tick_seconds=float(os.getenv("SIMULATION_TICK_SECONDS", "5")),
            generations_per_tick=int(os.getenv("GENERATIONS_PER_TICK", "1000")),
            simulation_random_seed=int(seed) if seed else None,
            dev_mode=_boolean("DEV_MODE", False),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
