from dataclasses import replace
from random import Random
from sqlalchemy import func, select
from app.config.game_balance import BALANCE
from app.engine import CONTENT
from app.events.definitions import evaluate_tick_events
from app.models.entities import GameEvent, Habitat, Species, World
from app.simulation.evolution import MutationBias, attempt_mutation
from backend.tests.simulation.test_service import build_world
from backend.tests.simulation.conftest import session  # noqa: F401


def test_world_first_is_once_per_world(session):
    world_id, species_id, _ = build_world(session)
    world, species = session.get(World, world_id), session.get(Species, species_id)
    species.generation = 10_000
    evaluate_tick_events(session, world, [species], Random(1), False, {})
    evaluate_tick_events(session, world, [species], Random(1), False, {})
    assert session.scalar(select(func.count()).select_from(GameEvent).where(
        GameEvent.code == "FIRST_STABLE_LIFE")) == 1


def test_major_adaptation_is_reachable_but_ordinary_mutation_is_below_threshold(session):
    world_id, species_id, _ = build_world(session)
    world, species = session.get(World, world_id), session.get(Species, species_id)
    habitat = session.get(Habitat, species.habitat_id)
    habitat.solar_energy = 100
    threshold = float(CONTENT["events"]["FIRST_MAJOR_ADAPTATION"].trigger.value)
    deterministic = replace(BALANCE, mutation_chance=1, beneficial_fixation_chance=1)
    bias = MutationBias("energy_efficiency", 1)

    species.population, species.energy_efficiency = 100, 5
    ordinary = attempt_mutation(species, habitat, Random(3), balance=deterministic, bias=bias)
    assert ordinary and 0 < ordinary.fitness_after - ordinary.fitness_before < threshold
    evaluate_tick_events(session, world, [species], Random(1), False, {species.id: ordinary})
    assert session.scalar(select(func.count()).select_from(GameEvent).where(
        GameEvent.code == "FIRST_MAJOR_ADAPTATION")) == 0

    species.population, species.energy_efficiency = 10, 5
    major = attempt_mutation(species, habitat, Random(3), balance=deterministic, bias=bias)
    assert major and major.fitness_after - major.fitness_before >= threshold
    evaluate_tick_events(session, world, [species], Random(1), False, {species.id: major})
    evaluate_tick_events(session, world, [species], Random(1), False, {species.id: major})
    assert session.scalar(select(func.count()).select_from(GameEvent).where(
        GameEvent.code == "FIRST_MAJOR_ADAPTATION")) == 1
