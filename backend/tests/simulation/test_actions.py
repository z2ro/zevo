from __future__ import annotations

import random
from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.config.game_balance import BALANCE, TRAIT_NAMES
from app.models.entities import Habitat, Player, PlayerAction, Species, SpeciesEvolution, SpeciesTraitHistory, World, WorldSnapshot
from app.models.enums import ActionStatus, ActionType, EnergySource, EvolutionStatus, SpeciesStatus, SpeciesType, Strategy, TraitChangeCause
from app.config.settings import Settings
from app.services.action_service import (
    ActionServiceError, active_focus_modifiers, change_strategy, complete_due_focuses,
    complete_due_migrations, queue_focus, queue_migration, split_species,
)
from app.services.species_service import abandon_species
from app.services.simulation_service import SimulationService
from app.services import simulation_service as simulation_module
from app.simulation.actions import apply_founder_effect, focus_duration, focus_modifiers


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
    assert action.execute_at_year == world.age_years + BALANCE.migration_duration_years
    assert species.habitat_id == source.id
    assert complete_due_migrations(session, world.id, world.age_years) == []
    completed = complete_due_migrations(session, world.id, world.age_years + 1_000)
    assert completed == [action]
    assert action.status is ActionStatus.COMPLETED
    assert species.habitat_id == destination.id
    assert species.population == round(1_000 * (1 - BALANCE.migration_mortality))


def test_migration_validates_destination_and_duplicate(session):
    world, source, destination, player, species = setup_state(session)
    raises_code("same_habitat", lambda: queue_migration(session, player.id, species.id, source.id))
    queue_migration(session, player.id, species.id, destination.id)
    raises_code("migration_pending", lambda: queue_migration(session, player.id, species.id, destination.id))


def test_abandon_fails_pending_control_actions(session):
    world, _, destination, player, species = setup_state(session)
    migration = queue_migration(session, player.id, species.id, destination.id)
    focus = queue_focus(session, player.id, species.id, ActionType.FOCUS_REPRODUCTION)
    abandon_species(session, player.id, species.id)
    assert species.status is SpeciesStatus.WILD
    assert migration.status is ActionStatus.FAILED and focus.status is ActionStatus.FAILED
    assert migration.payload["failure_reason"] == "species_abandoned"
    assert complete_due_migrations(session, world.id, world.age_years + 1_000) == []
    assert active_focus_modifiers(session, species.id, world.age_years + 1_000) == {
        "reproduction_modifier": 1.0, "mortality_modifier": 1.0}


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
    assert focus_modifiers("FOCUS_REPRODUCTION") == {
        "reproduction_modifier": 1.2, "mortality_modifier": 1.15,
    }
    assert focus_modifiers("FOCUS_SURVIVAL") == {
        "reproduction_modifier": 0.85, "mortality_modifier": 0.8,
    }


def test_strategy_changes_immediately_and_enforces_year_cooldown(session):
    world, _, _, player, species = setup_state(session)
    change_strategy(session, player.id, species.id, Strategy.RESISTANT)
    assert species.strategy is Strategy.RESISTANT
    raises_code("strategy_cooldown", lambda: change_strategy(session, player.id, species.id, Strategy.COMPETITOR))
    world.age_years += BALANCE.strategy_cooldown_years
    change_strategy(session, player.id, species.id, Strategy.COMPETITOR)
    assert species.strategy is Strategy.COMPETITOR


def test_focus_is_temporary_exclusive_and_has_tradeoff(session):
    world, _, _, player, species = setup_state(session)
    action = queue_focus(session, player.id, species.id, ActionType.FOCUS_REPRODUCTION)
    assert action.status is ActionStatus.PENDING
    assert action.execute_at_year == world.age_years + focus_duration(ActionType.FOCUS_REPRODUCTION.value)
    assert action.payload["modifiers"] == focus_modifiers("FOCUS_REPRODUCTION")
    assert action.payload["modifiers"]["reproduction_modifier"] > 1
    assert action.payload["modifiers"]["mortality_modifier"] > 1
    assert active_focus_modifiers(session, species.id, world.age_years) == action.payload["modifiers"]
    raises_code("focus_active", lambda: queue_focus(session, player.id, species.id, ActionType.FOCUS_SURVIVAL))
    assert complete_due_focuses(session, world.id, action.execute_at_year) == []
    assert action.status is ActionStatus.PENDING
    assert active_focus_modifiers(session, species.id, action.execute_at_year) == action.payload["modifiers"]
    assert complete_due_focuses(session, world.id, action.execute_at_year + 1) == [action]
    assert action.status is ActionStatus.COMPLETED
    assert active_focus_modifiers(session, species.id, action.execute_at_year + 1) == {"reproduction_modifier": 1.0, "mortality_modifier": 1.0}


def test_catchup_applies_migration_focus_and_adaptation_at_each_step(session, monkeypatch):
    world, _, destination, player, species = setup_state(session)
    migration = queue_migration(session, player.id, species.id, destination.id)
    focus = queue_focus(session, player.id, species.id, ActionType.FOCUS_REPRODUCTION)
    response = SpeciesEvolution(species_id=species.id, evolution_id="RADIATION_SHIELDING_I", level=1,
        status=EvolutionStatus.IN_PROGRESS, started_at_year=0, complete_at_year=12_000)
    session.add(response); session.flush()
    focus_by_age, bias_by_age, habitats, event_ages = {}, {}, [], []
    original_focus = simulation_module.active_focus_modifiers
    original_adaptive = simulation_module.active_adaptive_response
    original_simulate = simulation_module.simulate_species
    original_events = simulation_module.evaluate_tick_events

    def record_focus(db, species_id, age):
        result = original_focus(db, species_id, age); focus_by_age[age] = result; return result

    def record_adaptive(db, species_id, age):
        result = original_adaptive(db, species_id, age); bias_by_age[age] = result[0]; return result

    def record_habitat(candidate, habitat, *args, **kwargs):
        habitats.append(habitat.id); return original_simulate(candidate, habitat, *args, **kwargs)

    def record_events(db, event_world, *args, **kwargs):
        event_ages.append(event_world.age_years)
        return original_events(db, event_world, *args, **kwargs)

    monkeypatch.setattr(simulation_module, "active_focus_modifiers", record_focus)
    monkeypatch.setattr(simulation_module, "active_adaptive_response", record_adaptive)
    monkeypatch.setattr(simulation_module, "simulate_species", record_habitat)
    monkeypatch.setattr(simulation_module, "evaluate_tick_events", record_events)
    summary = SimulationService(Settings(database_url="", simulation_random_seed=7)).run_tick(
        session, world.id, now=world.last_simulated_at + timedelta(seconds=75))
    assert summary.steps_processed == 15
    assert migration.status is ActionStatus.COMPLETED and habitats == [destination.id] * 15
    assert all(focus_by_age[age]["reproduction_modifier"] > 1 for age in (1_000, 2_000, 3_000))
    assert all(focus_by_age[age]["reproduction_modifier"] == 1 for age in range(4_000, 16_000, 1_000))
    assert all(bias_by_age[age] is not None for age in range(1_000, 13_000, 1_000))
    assert all(bias_by_age[age] is None for age in range(13_000, 16_000, 1_000))
    assert focus.status is ActionStatus.COMPLETED and response.status is EvolutionStatus.COMPLETED
    assert event_ages == list(range(1_000, 16_000, 1_000))
    assert [row.age_years for row in session.scalars(select(WorldSnapshot).order_by(WorldSnapshot.tick))] == list(range(1_000, 16_000, 1_000))


def test_only_current_active_species_accepts_actions(session):
    _, _, destination, player, species = setup_state(session)
    species.status = SpeciesStatus.WILD
    species.is_player_controlled = False
    session.flush()
    raises_code("species_not_controlled", lambda: queue_migration(session, player.id, species.id, destination.id))
