from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import GameEvent, HistoricalFlag
from .core import EventContext, EventDefinition, EventEvaluator, EventResult, RepeatPolicy


_IDEMPOTENCY_METADATA_KEY = "_idempotency_key"
_REPEAT_SCOPE = {
    RepeatPolicy.ALWAYS: "ALWAYS",
    RepeatPolicy.ONCE_PER_WORLD: "WORLD",
    RepeatPolicy.ONCE_PER_SPECIES: "SPECIES",
    RepeatPolicy.ONCE_PER_PLAYER: "PLAYER",
}


class EventService:
    """Evaluate and atomically stage events/effects in the caller's transaction."""

    def __init__(self, session: Session, evaluator: EventEvaluator | None = None):
        self.session = session
        self.evaluator = evaluator or EventEvaluator()

    def evaluate_all(
        self,
        definitions: Iterable[EventDefinition],
        context: EventContext,
        *,
        idempotency_prefix: str | None = None,
    ) -> list[EventResult]:
        return [
            self.evaluate_and_persist(
                definition,
                context,
                idempotency_key=f"{idempotency_prefix}:{definition.code}" if idempotency_prefix else None,
            )
            for definition in definitions
        ]

    def evaluate_and_persist(
        self,
        definition: EventDefinition,
        context: EventContext,
        *,
        idempotency_key: str | None = None,
    ) -> EventResult:
        evaluated = self.evaluator.evaluate(definition, context)
        if not evaluated.matched:
            return evaluated
        duplicate = self._find_duplicate(definition, context, idempotency_key)
        if duplicate is not None:
            return EventResult(definition, True, False, duplicate.id, reason="duplicate")

        metadata = dict(definition.metadata_factory(context) if definition.metadata_factory else {})
        if idempotency_key:
            metadata[_IDEMPOTENCY_METADATA_KEY] = idempotency_key
        event = GameEvent(
            world_id=context.world.id,
            code=definition.code,
            name=definition.name,
            description=definition.description,
            rarity=definition.rarity,
            generation=context.world.generation,
            historical=definition.historical,
            global_unique=definition.global_unique or definition.repeat_policy == RepeatPolicy.ONCE_PER_WORLD,
            idempotency_key=idempotency_key,
            repeat_scope=_REPEAT_SCOPE[RepeatPolicy.ONCE_PER_WORLD if definition.global_unique else definition.repeat_policy],
            species_id=getattr(context.species, "id", None),
            player_id=getattr(context.player, "id", None),
            event_metadata=metadata,
        )
        effects: list[Mapping[str, Any]] = []
        try:
            with self.session.begin_nested():
                self.session.add(event)
                self.session.flush()
                for consequence in definition.consequences:
                    effect = consequence.apply(context)
                    if effect is not None:
                        effects.append(dict(effect))
                self.session.flush()
        except IntegrityError:
            duplicate = self._find_duplicate(definition, context, idempotency_key)
            return EventResult(
                definition, True, False, getattr(duplicate, "id", None), reason="duplicate"
            )
        return EventResult(definition, True, True, event.id, tuple(effects))

    def ensure_flag(
        self,
        context: EventContext,
        code: str,
        *,
        species_id: int | None = None,
        player_id: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HistoricalFlag:
        if species_id is not None and player_id is not None:
            raise ValueError("Historical flags can target species or player, not both")
        existing = self._find_flag(context.world.id, code, species_id, player_id)
        if existing:
            return existing
        flag = HistoricalFlag(
            world_id=context.world.id,
            species_id=species_id,
            player_id=player_id,
            code=code,
            generation=context.world.generation,
            flag_metadata=dict(metadata or {}),
        )
        try:
            with self.session.begin_nested():
                self.session.add(flag)
                self.session.flush()
        except IntegrityError:
            existing = self._find_flag(context.world.id, code, species_id, player_id)
            if existing is None:
                raise
            return existing
        return flag

    def _find_duplicate(
        self,
        definition: EventDefinition,
        context: EventContext,
        idempotency_key: str | None,
    ) -> GameEvent | None:
        query = select(GameEvent).where(
            GameEvent.world_id == context.world.id,
            GameEvent.code == definition.code,
        )
        policy = RepeatPolicy.ONCE_PER_WORLD if definition.global_unique else definition.repeat_policy
        if policy == RepeatPolicy.ONCE_PER_SPECIES:
            species_id = getattr(context.species, "id", None)
            if species_id is None:
                raise ValueError("ONCE_PER_SPECIES requires context.species")
            query = query.where(GameEvent.species_id == species_id)
        elif policy == RepeatPolicy.ONCE_PER_PLAYER:
            player_id = getattr(context.player, "id", None)
            if player_id is None:
                raise ValueError("ONCE_PER_PLAYER requires context.player")
            query = query.where(GameEvent.player_id == player_id)
        elif policy == RepeatPolicy.ALWAYS and idempotency_key is None:
            return None

        if policy == RepeatPolicy.ALWAYS:
            query = query.where(GameEvent.idempotency_key == idempotency_key)
        return self.session.scalar(query)

    def _find_flag(
        self,
        world_id: int,
        code: str,
        species_id: int | None,
        player_id: int | None,
    ) -> HistoricalFlag | None:
        query = select(HistoricalFlag).where(
            HistoricalFlag.world_id == world_id,
            HistoricalFlag.code == code,
        )
        query = query.where(
            HistoricalFlag.species_id.is_(None) if species_id is None else HistoricalFlag.species_id == species_id,
            HistoricalFlag.player_id.is_(None) if player_id is None else HistoricalFlag.player_id == player_id,
        )
        return self.session.scalar(query)
