from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from random import Random
from typing import Any, Callable, Mapping, Protocol, Sequence

from app.models.enums import EventRarity
from .conditions import Condition


class RepeatPolicy(StrEnum):
    ALWAYS = "ALWAYS"
    ONCE_PER_WORLD = "ONCE_PER_WORLD"
    ONCE_PER_SPECIES = "ONCE_PER_SPECIES"
    ONCE_PER_PLAYER = "ONCE_PER_PLAYER"


@dataclass
class EventContext:
    world: Any
    rng: Random
    dev_mode: bool = False
    species: Any | None = None
    player: Any | None = None
    values: Mapping[str, Any] = field(default_factory=dict)

    def resolve(self, path: str) -> Any:
        parts = path.split(".")
        roots = {"world": self.world, "species": self.species, "player": self.player, **self.values}
        if parts[0] not in roots:
            raise KeyError(parts[0])
        value = roots[parts[0]]
        for part in parts[1:]:
            value = value.get(part) if isinstance(value, Mapping) else getattr(value, part)
        return value


class EventConsequence(Protocol):
    def apply(self, context: EventContext) -> Mapping[str, Any] | None: ...


@dataclass(frozen=True)
class CallbackConsequence:
    name: str
    function: Callable[[EventContext], Mapping[str, Any] | None]

    def apply(self, context: EventContext) -> Mapping[str, Any] | None:
        return self.function(context)


MetadataFactory = Callable[[EventContext], Mapping[str, Any]]


@dataclass(frozen=True)
class EventDefinition:
    code: str
    name: str
    description: str
    rarity: EventRarity
    condition: Condition
    consequences: Sequence[EventConsequence] = ()
    historical: bool = True
    global_unique: bool = False
    repeat_policy: RepeatPolicy = RepeatPolicy.ALWAYS
    metadata_factory: MetadataFactory | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.code.replace("_", "").isalnum() or self.code != self.code.upper():
            raise ValueError("Event code must be non-empty uppercase letters, digits, or underscores")
        if self.global_unique and self.repeat_policy not in (RepeatPolicy.ALWAYS, RepeatPolicy.ONCE_PER_WORLD):
            raise ValueError("A global unique event cannot use a subject repeat policy")


@dataclass(frozen=True)
class EventResult:
    definition: EventDefinition
    matched: bool
    persisted: bool = False
    event_id: int | None = None
    effects: tuple[Mapping[str, Any], ...] = ()
    reason: str | None = None


class EventEvaluator:
    def evaluate(self, definition: EventDefinition, context: EventContext) -> EventResult:
        matched = definition.condition.evaluate(context)
        return EventResult(
            definition=definition,
            matched=matched,
            reason=None if matched else "condition_not_met",
        )
