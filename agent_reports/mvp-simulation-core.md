# Task

`mvp-simulation-core`

# Agent

Simulation Agent

# Status

FIXED — review findings addressed, validation passed; ready for re-review.

# Summary

Implemented deterministic, frontend-independent simulation primitives for fitness and viability preview, bounded logistic population updates, mutation/selection, bottleneck variance, extinction, environmental feedback, snapshots, and a transactional tick adapter. ACTIVE and WILD species share the exact same tick path; only EXTINCT species are excluded.

Review correction cycle additionally isolates species queries by world, guarantees the ±35% population delta even above carrying capacity, propagates injected balance through selection, centralizes all adjustable simulation coefficients, and persists post-mutation fitness consistently with post-mutation traits.

# Files changed

- `backend/app/simulation/__init__.py`
- `backend/app/config/game_balance.py` (explicit Orchestrator scope exception, now present in task scope)
- `backend/app/simulation/common.py`
- `backend/app/simulation/fitness.py`
- `backend/app/simulation/population.py`
- `backend/app/simulation/evolution.py`
- `backend/app/simulation/engine.py`
- `backend/app/services/simulation_service.py`
- `backend/tests/simulation/conftest.py`
- `backend/tests/simulation/test_core.py`
- `backend/tests/simulation/test_service.py`
- `agent_reports/mvp-simulation-core.md`

# Contracts changed

None. Public API, persistent models, docs, graph, events, and frontend were not modified.

# Tests

- `python3 -m pytest backend/tests/simulation -q` — `15 passed`
- `python3 -m compileall -q backend/app/simulation backend/app/services/simulation_service.py` — passed
- Explicit scope validation over all task-owned paths — passed

Coverage includes positive/negative fitness trends, preview opacity, carrying-capacity and absolute delta bounds including over-capacity populations, parasite host penalty primitive, deterministic mutation, injected balance propagation, bottleneck magnitude, trait-budget preservation, extinction, WILD ticking, multi-world isolation, consistent post-mutation snapshots/history, generation advancement, and replay from identical seed/state.

# Failures

None remaining.

# Risks

- Competition and host compatibility are accepted as explicit `FitnessContext` inputs. Their calculation and persistence belong to later competition/parasitism tasks; the base tick currently supplies neutral competition/no host.
- Tick locking uses `SELECT ... FOR UPDATE`; SQLite unit tests validate behavior but not PostgreSQL lock contention.
- The persistent model enforces the initial 100-point trait budget for the full species lifetime. Mutation therefore preserves that database invariant, which constrains adaptation to redistribution/loss at the ceiling.

# Notes for next agent

- Competition/parasitism should compute contexts from a pre-tick snapshot and pass them to `simulate_species`, avoiding species-order effects.
- Event engine should consume persisted trait/population snapshots and changes; it should not duplicate mutation or fitness calculations.
- Backend API preview can call `preview_fitness` with an unsaved species-like object.
- Scheduler/API transaction owners must commit or roll back around `SimulationService.run_tick`; the service intentionally only flushes.
