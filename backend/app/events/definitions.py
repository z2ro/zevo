from __future__ import annotations

from random import Random
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE
from app.engine import CONTENT
from app.engine.content import evaluate_condition
from app.models.entities import Player, Species, SpeciesRelation, World
from app.models.enums import EventRarity, RelationType, SpeciesStatus, SpeciesType
from .conditions import Predicate
from app.engine.effects import EffectExecutionContext, execute_effects
from .core import CallbackConsequence, EventContext, EventDefinition, RepeatPolicy
from .service import EventService


def _world_first(code: str, condition) -> EventDefinition:
    spec = CONTENT["events"][code]
    return EventDefinition(code, spec.name, spec.description, EventRarity(spec.rarity), condition,
        global_unique=spec.global_unique, repeat_policy=RepeatPolicy(spec.repeat_policy),
        metadata_factory=lambda ctx: dict(ctx.values.get("metadata", {})))


def evaluate_tick_events(session: Session, world: World, species: list[Species], rng: Random,
                         dev_mode: bool, mutations: dict[int, object]) -> int:
    service, created = EventService(session), 0
    players = {p.id: p for p in session.scalars(select(Player))}
    living = {s.id: s for s in species if s.status != SpeciesStatus.EXTINCT and s.population > 0}
    relations = list(session.scalars(select(SpeciesRelation).where(
        SpeciesRelation.relation_type == RelationType.PARASITISM)))

    for relation in relations:
        gray = CONTENT["events"]["gray_blood"]
        parasite, host = living.get(relation.predator_or_parasite_id), living.get(relation.target_species_id)
        if not parasite or not host or parasite.habitat_id != host.habitat_id:
            continue

        def harm(ctx, target=host, source=parasite):
            results = execute_effects(gray.effects, EffectExecutionContext(
                world=world, species=source, host=target, parasite=source,
                relation=relation, event_context=ctx, event_service=service))
            loss = next((abs(result["population_delta"]) for result in results if "population_delta" in result), 0)
            return {"host_population_loss": loss, "evolutionary_pressure": "HIGH"}

        metadata = {"parasite_species_id": parasite.id, "host_species_id": host.id,
            "parasite_original_creator_id": parasite.creator_id, "host_creator_id": host.creator_id,
            "habitat_id": host.habitat_id, "generation": world.generation}
        context = EventContext(world, rng, dev_mode, parasite, players.get(parasite.creator_id),
                               {"relation": relation, "host": host, "metadata": metadata})
        values = {"parasite.species_type": parasite.species_type.value,
                  "parasite.mutation_rate": parasite.mutation_rate,
                  "host.population": host.population,
                  "relation.infection_rate": relation.infection_rate,
                  "relation.transmission_rate": relation.transmission_rate}
        condition = Predicate(
            "declarative_gray_blood",
            lambda c, spec=gray.trigger, vals=values: evaluate_condition(spec, vals)
            and c.rng.random() < min(1.0, gray.chance *
                                    (BALANCE.gray_blood_dev_multiplier if c.dev_mode else 1.0)),
        )
        definition = EventDefinition(
            "GRAY_BLOOD", gray.name, gray.description,
            EventRarity(gray.rarity), condition,
            (CallbackConsequence("declarative_effects", harm),),
            metadata_factory=lambda c, data=metadata: data,
        )
        created += int(service.evaluate_and_persist(
            definition, context, idempotency_key=f"{world.tick}:{parasite.id}:{host.id}").persisted)

    candidates = sorted(living.values(), key=lambda item: item.id)
    stable_spec = CONTENT["events"]["FIRST_STABLE_LIFE"]
    stable = next((s for s in candidates if evaluate_condition(stable_spec.trigger, {"species.generation": s.generation})), None)
    successful_relation = next((r for r in relations if r.strength > 0 and living.get(r.predator_or_parasite_id)), None)
    successful = living.get(successful_relation.predator_or_parasite_id) if successful_relation else None
    major_spec = CONTENT["events"]["FIRST_MAJOR_ADAPTATION"]
    major = next((living.get(sid) for sid, change in mutations.items()
                  if evaluate_condition(major_spec.trigger, {"mutation.fitness_delta": change.fitness_after - change.fitness_before})), None)
    firsts = (("FIRST_STABLE_LIFE", stable, {"species.generation": getattr(stable, "generation", None)}),
              ("FIRST_SUCCESSFUL_PARASITE", successful, {"relation.strength": getattr(successful_relation, "strength", None)}),
              ("FIRST_MAJOR_ADAPTATION", major, {"mutation.fitness_delta": (major and mutations[major.id].fitness_after - mutations[major.id].fitness_before)}))
    for code, subject, values in firsts:
        if subject:
            spec = CONTENT["events"][code]
            definition = _world_first(code, Predicate(code, lambda _, spec=spec, values=values: evaluate_condition(spec.trigger, values)))
            context = EventContext(world, rng, dev_mode, subject, players.get(subject.creator_id),
                {"metadata": {"species_id": subject.id, "player_id": subject.creator_id}})
            created += int(service.evaluate_and_persist(definition, context).persisted)
    return created
