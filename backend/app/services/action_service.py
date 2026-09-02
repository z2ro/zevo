from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.game_balance import BALANCE
from app.models.entities import Habitat, PlayerAction, Species, SpeciesTraitHistory, World
from app.models.enums import ActionStatus, ActionType, SpeciesStatus, Strategy, TraitChangeCause
from app.simulation.actions import apply_founder_effect, focus_duration, focus_modifiers, migration_population, split_population


@dataclass(frozen=True)
class ActionServiceError(Exception):
    code: str
    message: str
    status_code: int = 409

    def __str__(self) -> str:
        return self.message


def _controlled_species(session: Session, player_id: int, species_id: int) -> Species:
    species = session.scalar(select(Species).where(Species.id == species_id).with_for_update())
    if species is None:
        raise ActionServiceError("species_not_found", "Species does not exist", 404)
    if species.creator_id != player_id or not species.is_player_controlled or species.status is not SpeciesStatus.ACTIVE:
        raise ActionServiceError("species_not_controlled", "Only the player's current ACTIVE species accepts commands")
    return species


def _world_for_habitat(session: Session, habitat_id: int) -> World:
    world = session.scalar(
        select(World).join(Habitat, Habitat.world_id == World.id).where(Habitat.id == habitat_id)
    )
    if world is None:
        raise ActionServiceError("world_not_found", "Species habitat has no world", 404)
    return world


def queue_migration(session: Session, player_id: int, species_id: int, destination_habitat_id: int) -> PlayerAction:
    species = _controlled_species(session, player_id, species_id)
    destination = session.get(Habitat, destination_habitat_id)
    if destination is None:
        raise ActionServiceError("habitat_not_found", "Destination habitat does not exist", 404)
    world = _world_for_habitat(session, species.habitat_id)
    if destination.world_id != world.id:
        raise ActionServiceError("cross_world_migration", "Migration destination must be in the same world")
    if destination.id == species.habitat_id:
        raise ActionServiceError("same_habitat", "Migration requires a different destination")
    existing = session.scalar(select(PlayerAction.id).where(
        PlayerAction.species_id == species.id, PlayerAction.action_type == ActionType.MIGRATE,
        PlayerAction.status == ActionStatus.PENDING,
    ))
    if existing is not None:
        raise ActionServiceError("migration_pending", "Species already has a pending migration")
    action = PlayerAction(
        player_id=player_id, species_id=species.id, action_type=ActionType.MIGRATE,
        status=ActionStatus.PENDING, execute_at_tick=world.tick + BALANCE.migration_duration_ticks,
        payload={"origin_habitat_id": species.habitat_id, "destination_habitat_id": destination.id},
    )
    session.add(action); session.flush()
    return action


def complete_due_migrations(session: Session, world_id: int, current_tick: int) -> list[PlayerAction]:
    actions = list(session.scalars(
        select(PlayerAction)
        .join(Species, PlayerAction.species_id == Species.id)
        .join(Habitat, Species.habitat_id == Habitat.id)
        .where(Habitat.world_id == world_id, PlayerAction.action_type == ActionType.MIGRATE,
               PlayerAction.status == ActionStatus.PENDING, PlayerAction.execute_at_tick <= current_tick)
        .order_by(PlayerAction.id)
        .with_for_update()
    ))
    completed: list[PlayerAction] = []
    for action in actions:
        species = session.get(Species, action.species_id)
        destination = session.get(Habitat, int(action.payload["destination_habitat_id"]))
        if (species is None or destination is None or species.status is not SpeciesStatus.ACTIVE
                or not species.is_player_controlled):
            action.status = ActionStatus.FAILED
            action.completed_at = datetime.now(timezone.utc)
            action.payload = {**action.payload, "failure_reason": "species_abandoned"}
            continue
        species.population = migration_population(species.population)
        species.habitat_id = destination.id
        action.status = ActionStatus.COMPLETED
        action.completed_at = datetime.now(timezone.utc)
        completed.append(action)
    session.flush()
    return completed


def split_species(session: Session, player_id: int, species_id: int, population_fraction: float | None = None, *, seed: int = 0) -> Species:
    population_fraction = BALANCE.founder_expedition_fraction if population_fraction is None else population_fraction
    if not 0 < population_fraction < 1:
        raise ActionServiceError("invalid_population_fraction", "Split fraction must be in (0, 1)")
    species = _controlled_species(session, player_id, species_id)
    species.population = split_population(species.population, population_fraction)
    changes = apply_founder_effect(species, random.Random(f"{seed}:{species.id}:{species.generation}"))
    for change in changes:
        session.add(SpeciesTraitHistory(
            species_id=species.id, generation=species.generation, trait=change.trait,
            old_value=change.old_value, new_value=change.new_value,
            cause=TraitChangeCause.FOUNDER_EFFECT,
        ))
    session.add(PlayerAction(
        player_id=player_id, species_id=species.id, action_type=ActionType.SPLIT_POPULATION,
        status=ActionStatus.COMPLETED, completed_at=datetime.now(timezone.utc),
        payload={"population_fraction": population_fraction, "founder_changes": len(changes)},
    ))
    session.flush()
    return species


def change_strategy(session: Session, player_id: int, species_id: int, strategy: Strategy) -> Species:
    species = _controlled_species(session, player_id, species_id)
    world = _world_for_habitat(session, species.habitat_id)
    if species.strategy is strategy:
        raise ActionServiceError("strategy_unchanged", "New strategy must differ from current strategy")
    if species.species_type.value == "PARASITIC" and strategy is not Strategy.PARASITE:
        raise ActionServiceError("invalid_parasite_strategy", "PARASITIC species must use PARASITE strategy")
    previous = session.scalar(select(PlayerAction).where(
        PlayerAction.species_id == species.id,
        PlayerAction.action_type == ActionType.CHANGE_STRATEGY,
        PlayerAction.status == ActionStatus.COMPLETED,
    ).order_by(PlayerAction.id.desc()))
    if previous and int(previous.payload.get("cooldown_until_tick", 0)) > world.tick:
        raise ActionServiceError("strategy_cooldown", "Strategy change is on cooldown")
    old = species.strategy.value
    species.strategy = strategy
    session.add(PlayerAction(
        player_id=player_id, species_id=species.id, action_type=ActionType.CHANGE_STRATEGY,
        status=ActionStatus.COMPLETED, completed_at=datetime.now(timezone.utc),
        payload={"old_strategy": old, "new_strategy": strategy.value,
                 "cooldown_until_tick": world.tick + BALANCE.strategy_cooldown_ticks},
    ))
    session.flush()
    return species


def queue_focus(session: Session, player_id: int, species_id: int, action_type: ActionType) -> PlayerAction:
    if action_type not in (ActionType.FOCUS_REPRODUCTION, ActionType.FOCUS_SURVIVAL):
        raise ActionServiceError("invalid_focus", "Unsupported focus action")
    species = _controlled_species(session, player_id, species_id)
    world = _world_for_habitat(session, species.habitat_id)
    existing = session.scalar(select(PlayerAction.id).where(
        PlayerAction.species_id == species.id,
        PlayerAction.action_type.in_((ActionType.FOCUS_REPRODUCTION, ActionType.FOCUS_SURVIVAL)),
        PlayerAction.status == ActionStatus.PENDING,
    ))
    if existing is not None:
        raise ActionServiceError("focus_active", "Species already has an active focus")
    action = PlayerAction(
        player_id=player_id, species_id=species.id, action_type=action_type,
        status=ActionStatus.PENDING, execute_at_tick=world.tick + focus_duration(action_type.value),
        payload={"modifiers": focus_modifiers(action_type.value), "started_at_tick": world.tick},
    )
    session.add(action); session.flush()
    return action


def active_focus_modifiers(session: Session, species_id: int, current_tick: int) -> dict[str, float]:
    species = session.get(Species, species_id)
    if species is None or species.status is not SpeciesStatus.ACTIVE or not species.is_player_controlled:
        return {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}
    action = session.scalar(select(PlayerAction).where(
        PlayerAction.species_id == species_id,
        PlayerAction.action_type.in_((ActionType.FOCUS_REPRODUCTION, ActionType.FOCUS_SURVIVAL)),
        PlayerAction.status == ActionStatus.PENDING,
        PlayerAction.execute_at_tick >= current_tick,
    ).order_by(PlayerAction.id.desc()))
    return dict(action.payload["modifiers"]) if action else {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}


def complete_due_focuses(session: Session, world_id: int, current_tick: int) -> list[PlayerAction]:
    actions = list(session.scalars(
        select(PlayerAction)
        .join(Species, PlayerAction.species_id == Species.id)
        .join(Habitat, Species.habitat_id == Habitat.id)
        .where(Habitat.world_id == world_id,
               PlayerAction.action_type.in_((ActionType.FOCUS_REPRODUCTION, ActionType.FOCUS_SURVIVAL)),
               PlayerAction.status == ActionStatus.PENDING,
               PlayerAction.execute_at_tick < current_tick)
        .order_by(PlayerAction.id)
        .with_for_update()
    ))
    now = datetime.now(timezone.utc)
    for action in actions:
        action.status = ActionStatus.COMPLETED
        action.completed_at = now
    session.flush()
    return actions
