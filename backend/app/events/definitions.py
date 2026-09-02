from __future__ import annotations

from random import Random
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine import CONTENT
from app.engine.content import evaluate_condition
from app.engine.effects import EffectExecutionContext, execute_effects
from app.events.candidates import EventCandidate, event_candidates
from app.models.entities import Player, Species, SpeciesRelation, World
from app.models.enums import EventRarity, RelationType
from .conditions import Predicate
from .core import CallbackConsequence, EventContext, EventDefinition, RepeatPolicy
from .service import EventService


def _definition(spec, candidate: EventCandidate, world: World, rng: Random, dev_mode: bool, service: EventService):
    def condition(_context):
        if not evaluate_condition(spec.trigger, candidate.values):
            return False
        return spec.chance is None or rng.random() < min(1.0, spec.chance * (spec.dev_chance_multiplier if dev_mode else 1.0))

    consequences = ()
    if spec.effects:
        def apply_effects(context):
            results = execute_effects(spec.effects, EffectExecutionContext(
                world=world, species=candidate.species, host=candidate.host,
                parasite=candidate.parasite, relation=candidate.relation,
                event_context=context, event_service=service))
            loss = next((abs(item["population_delta"]) for item in results if "population_delta" in item), 0)
            return {"host_population_loss": loss, "evolutionary_pressure": "HIGH"} if loss else {"effects": results}
        consequences = (CallbackConsequence("declarative_effects", apply_effects),)

    return EventDefinition(
        spec.id, spec.name, spec.description, EventRarity(spec.rarity), Predicate(spec.id, condition),
        consequences, global_unique=spec.global_unique,
        repeat_policy=RepeatPolicy(spec.repeat_policy),
        metadata_factory=lambda _: dict(candidate.metadata),
    )


def evaluate_tick_events(session: Session, world: World, species: list[Species], rng: Random,
                         dev_mode: bool, mutations: dict[int, object]) -> int:
    service = EventService(session)
    players = {p.id: p for p in session.scalars(select(Player))}
    relations = list(session.scalars(select(SpeciesRelation).where(
        SpeciesRelation.relation_type == RelationType.PARASITISM)))
    created = 0
    runtime = (species, players, relations, mutations, world)
    for spec in sorted(CONTENT["events"].values(), key=lambda item: item.id):
        for candidate in event_candidates(spec.scope, *runtime):
            context = EventContext(world, rng, dev_mode, candidate.species, candidate.player,
                                   {**candidate.values, "relation": candidate.relation,
                                    "host": candidate.host, "parasite": candidate.parasite,
                                    "metadata": candidate.metadata})
            definition = _definition(spec, candidate, world, rng, dev_mode, service)
            key = f"{spec.id}:{world.tick}:{candidate.identity}"
            created += int(service.evaluate_and_persist(definition, context, idempotency_key=key).persisted)
    return created
