from __future__ import annotations

import random
from dataclasses import replace
from types import SimpleNamespace

from sqlalchemy import select

from app.config.game_balance import BALANCE, TRAIT_NAMES
from app.models.entities import Habitat, Player, PlayerAction, Species, SpeciesTraitHistory, World
from app.models.enums import ActionStatus, ActionType, EnergySource, SpeciesStatus, SpeciesType, Strategy, TraitChangeCause
from app.services.action_service import (
    ActionServiceError, active_focus_modifiers, change_strategy, complete_due_focuses,
    complete_due_migrations, queue_focus, queue_migration, split_species,
)
from app.simulation.actions import apply_founder_effect, focus_modifiers


def setup_state(session):
    world = World(name="Eos-actions", generation=0, tick=10, temperature=50, oxygen=1, co2=70,
                  radiation=30, water_availability=80, average_ph=5, solar_energy=70,
                  chemical_energy=60, geological_activity=50)
    session.add(world); session.flush()
    source = Habitat(world_id=world.id, name="Source", temperature=40, radiation=20, ph=5,
                     water=90, solar_energy=90, chemical_energy=60, organic_resources=70,
                     carrying_capacity=10_000)
    destination = Habitat(world_id=world.id, name="Destination", temperature=20, radiation=10, ph=7,
                          water=80, solar_energy=70, chemical_energy=50, organic_resources=60,
                          carrying_capacity=8_000)
    player = Player(username="ActionPlayer")
    session.add_all([source, destination, player]); session.flush()
    species = Species(
        name="Mover", creator_id=player.id, habitat_id=source.id,
        species_type=SpeciesType.AUTOTROPH, status=SpeciesStatus.ACTIVE,
        is_player_controlled=True, population=1_000, generation=2_000, fitness=1.1,
        strategy=Strategy.COLONIZER, energy_source=EnergySource.SOLAR,
        thermal_tolerance=20, radiation_tolerance=10, ph_tolerance=10,
        metabolic_efficiency=15, reproduction_rate=15, mutation_rate=10,
        energy_efficiency=10, structural_resistance=10,
    )
    session.add(species); session.commit()
    return world, source, destination, player, species


def raises_code(code, callable_):
    try:
        callable_()
    except ActionServiceError as exc:
        assert exc.code == code
    else:
        raise AssertionError(f"Expected ActionServiceError({code})")


def test_migration_is_pending_then_completes_with_mortality(session):
    world, source, destination, player, species = setup_state(session)
    action = queue_migration(session, player.id, species.id, destination.id)
    assert action.status is ActionStatus.PENDING
    assert action.execute_at_tick == world.tick + BALANCE.migration_duration_ticks
    assert species.habitat_id == source.id
    assert complete_due_migrations(session, world.id, world.tick) == []
    completed = complete_due_migrations(session, world.id, world.tick + 1)
    assert completed == [action]
    assert action.status is ActionStatus.COMPLETED
    assert species.habitat_id == destination.id
    assert species.population == round(1_000 * (1 - BALANCE.migration_mortality))


def test_migration_validates_destination_and_duplicate(session):
    world, source, destination, player, species = setup_state(session)
    raises_code("same_habitat", lambda: queue_migration(session, player.id, species.id, source.id))
    queue_migration(session, player.id, species.id, destination.id)
    raises_code("migration_pending", lambda: queue_migration(session, player.id, species.id, destination.id))


def test_split_applies_loss_and_persists_founder_effect(session):
    _, _, _, player, species = setup_state(session)
    original = {name: getattr(species, name) for name in (
        "thermal_tolerance", "radiation_tolerance", "ph_tolerance", "metabolic_efficiency",
        "reproduction_rate", "mutation_rate", "energy_efficiency", "structural_resistance")}
    split_species(session, player.id, species.id, 0.25, seed=8)
    assert species.population == 988
    histories = list(session.scalars(select(SpeciesTraitHistory)))
    assert 1 <= len(histories) <= 2
    assert all(row.cause is TraitChangeCause.FOUNDER_EFFECT for row in histories)
    assert any(getattr(species, row.trait) != original[row.trait] for row in histories)
    action = session.scalar(select(PlayerAction).where(PlayerAction.action_type == ActionType.SPLIT_POPULATION))
    assert action.status is ActionStatus.COMPLETED


def test_split_is_deterministic_and_rejects_boundaries(session):
    _, _, _, player, species = setup_state(session)
    raises_code("invalid_population_fraction", lambda: split_species(session, player.id, species.id, 1))
    first = split_species(session, player.id, species.id, 0.2, seed=99)
    values = (first.thermal_tolerance, first.radiation_tolerance, first.ph_tolerance)
    session.rollback()
    # State committed by setup_state is restored; the same seed/state replays.
    replay = split_species(session, player.id, species.id, 0.2, seed=99)
    assert (replay.thermal_tolerance, replay.radiation_tolerance, replay.ph_tolerance) == values


def test_founder_effect_always_changes_zero_traits():
    candidate = SimpleNamespace(**{name: 0 for name in TRAIT_NAMES})
    changes = apply_founder_effect(candidate, random.Random(1))
    assert 1 <= len(changes) <= 2
    assert all(change.new_value > change.old_value for change in changes)


def test_founder_effect_changes_trait_at_upper_boundary_and_preserves_budget():
    traits = {name: 0 for name in TRAIT_NAMES}
    traits[TRAIT_NAMES[0]] = 100
    candidate = SimpleNamespace(**traits)
    changes = apply_founder_effect(candidate, random.Random(4))
    assert 1 <= len(changes) <= 2
    assert all(change.new_value != change.old_value for change in changes)
    assert sum(getattr(candidate, name) for name in TRAIT_NAMES) <= BALANCE.trait_budget


def test_focus_modifiers_use_injected_balance():
    custom = replace(BALANCE, focus_bonus=0.5, focus_penalty=0.4)
    assert focus_modifiers("FOCUS_REPRODUCTION", balance=custom) == {
        "reproduction_modifier": 1.5, "mortality_modifier": 1.4,
    }


def test_strategy_changes_immediately_and_enforces_tick_cooldown(session):
    world, _, _, player, species = setup_state(session)
    change_strategy(session, player.id, species.id, Strategy.RESISTANT)
    assert species.strategy is Strategy.RESISTANT
    raises_code("strategy_cooldown", lambda: change_strategy(session, player.id, species.id, Strategy.COMPETITOR))
    world.tick += BALANCE.strategy_cooldown_ticks
    change_strategy(session, player.id, species.id, Strategy.COMPETITOR)
    assert species.strategy is Strategy.COMPETITOR


def test_focus_is_temporary_exclusive_and_has_tradeoff(session):
    world, _, _, player, species = setup_state(session)
    action = queue_focus(session, player.id, species.id, ActionType.FOCUS_REPRODUCTION)
    assert action.status is ActionStatus.PENDING
    assert action.execute_at_tick == world.tick + BALANCE.focus_duration_ticks
    assert action.payload["modifiers"] == focus_modifiers("FOCUS_REPRODUCTION")
    assert action.payload["modifiers"]["reproduction_modifier"] > 1
    assert action.payload["modifiers"]["mortality_modifier"] > 1
    assert active_focus_modifiers(session, species.id, world.tick) == action.payload["modifiers"]
    raises_code("focus_active", lambda: queue_focus(session, player.id, species.id, ActionType.FOCUS_SURVIVAL))
    assert complete_due_focuses(session, world.id, action.execute_at_tick) == []
    assert action.status is ActionStatus.PENDING
    assert active_focus_modifiers(session, species.id, action.execute_at_tick) == action.payload["modifiers"]
    assert complete_due_focuses(session, world.id, action.execute_at_tick + 1) == [action]
    assert action.status is ActionStatus.COMPLETED
    assert active_focus_modifiers(session, species.id, action.execute_at_tick + 1) == {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}


def test_only_current_active_species_accepts_actions(session):
    _, _, destination, player, species = setup_state(session)
    species.status = SpeciesStatus.WILD
    species.is_player_controlled = False
    session.flush()
    raises_code("species_not_controlled", lambda: queue_migration(session, player.id, species.id, destination.id))
