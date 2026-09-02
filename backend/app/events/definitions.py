from __future__ import annotations

from random import Random
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE
from app.engine import CONTENT
from app.engine.content import evaluate_condition
from app.models.entities import Player, Species, SpeciesRelation, World
from app.models.enums import EventRarity, RelationType, SpeciesStatus, SpeciesType
from .conditions import All, Predicate, RandomRoll
from .core import CallbackConsequence, EventContext, EventDefinition, RepeatPolicy
from .service import EventService


def _world_first(code: str, name: str, condition) -> EventDefinition:
    return EventDefinition(code, name, name, EventRarity.WORLD_FIRST, condition,
        global_unique=True, repeat_policy=RepeatPolicy.ONCE_PER_WORLD,
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
            loss = 0
            for effect in gray.effects:
                if effect.type == "modify_population" and effect.target == "host":
                    before = target.population
                    target.population = max(0, int(before * (effect.multiplier or 1.0)))
                    loss = before - target.population
                elif effect.type == "add_historical_flag" and effect.target == "host":
                    service.ensure_flag(ctx, effect.flag, species_id=target.id,
                                        metadata={"parasite_species_id": source.id})
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
            and c.rng.random() < min(1.0, (gray.chance or 0.0) *
                                    (BALANCE.gray_blood_dev_multiplier if c.dev_mode else 1.0)),
        )
        definition = EventDefinition(
            "GRAY_BLOOD", gray.name or "Sangue Cinza",
            gray.description or "Uma linhagem parasitária desencadeou Sangue Cinza.",
            EventRarity.LEGENDARY, condition,
            (CallbackConsequence("declarative_effects", harm),),
            metadata_factory=lambda c, data=metadata: data,
        )
        created += int(service.evaluate_and_persist(
            definition, context, idempotency_key=f"{world.tick}:{parasite.id}:{host.id}").persisted)

    candidates = sorted(living.values(), key=lambda item: item.id)
    stable = next((s for s in candidates if s.generation >= BALANCE.stable_life_generations), None)
    successful = next((living.get(r.predator_or_parasite_id) for r in relations if r.strength > 0), None)
    major = next((living.get(sid) for sid, change in mutations.items()
                  if change.fitness_after - change.fitness_before >= BALANCE.major_adaptation_delta), None)
    for definition, subject in (
        (_world_first("FIRST_STABLE_LIFE", "First Stable Life", Predicate("stable", lambda _: stable is not None)), stable),
        (_world_first("FIRST_SUCCESSFUL_PARASITE", "First Successful Parasite", Predicate("parasite", lambda _: successful is not None)), successful),
        (_world_first("FIRST_MAJOR_ADAPTATION", "First Major Adaptation", Predicate("adaptation", lambda _: major is not None)), major),
    ):
        if subject:
            context = EventContext(world, rng, dev_mode, subject, players.get(subject.creator_id),
                {"metadata": {"species_id": subject.id, "player_id": subject.creator_id}})
            created += int(service.evaluate_and_persist(definition, context).persisted)
    return created
