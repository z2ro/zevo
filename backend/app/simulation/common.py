from __future__ import annotations


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def trait_values(species: object) -> dict[str, int]:
    from app.config.game_balance import TRAIT_NAMES

    return {name: int(getattr(species, name)) for name in TRAIT_NAMES}
