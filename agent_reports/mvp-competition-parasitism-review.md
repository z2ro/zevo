# Review: mvp-competition-parasitism

status: FAIL

severity: high

## Scope reviewed

- Task: `mvp-competition-parasitism`
- Agent: Simulation Agent
- Contracts: `docs/domain-model.md`, `docs/simulation-rules.md`, `docs/decisions.md`
- Implementation: `backend/app/simulation/interactions.py`
- Tests: `backend/tests/simulation/test_interactions.py` and adjacent simulation suite
- Handoff: `agent_reports/mvp-competition-parasitism.md`

## Issues

### 1. Competition and parasitism are not integrated into the simulation tick

- Severity: high
- Files: `backend/app/simulation/interactions.py`, `backend/app/services/simulation_service.py`, `backend/app/simulation/engine.py`, `graph/tasks.yaml`
- Evidence: repository search finds `fitness_context_for` and `persist_parasitism_relation` only in their definitions and unit tests. `SimulationService.run_tick()` still calls `simulate_species(species, habitat, rng, ...)` without an interaction context and never evaluates or persists parasite-host relations.
- Impact: in the playable simulation, co-located competitors do not reduce fitness, parasites always receive the no-host fitness penalty, no parasitism relation is created, and downstream GRAY_BLOOD cannot arise naturally. The implementation currently proves isolated formulas, not the required behavior.
- Recommended action: return this task to implementation with an Orchestrator-approved scope including the tick integration file(s), or create a blocking integration task before events/bots/API. For each habitat/tick, compute contexts from the same pre-update living-species snapshot, inject them into fitness, evaluate host establishment with the tick RNG and persist established relations within the tick transaction. Add service-level tests proving ACTIVE and WILD behavior.

### 2. Important interaction coefficients are hard-coded outside balance configuration

- Severity: high
- Files: `backend/app/simulation/interactions.py`, `backend/app/config/game_balance.py`, `docs/simulation-rules.md`
- Evidence: host abundance divisor `1_000`, compatibility weights `0.30/0.25/0.20/0.15/0.10`, compatibility threshold `0.25`, transmission divisor `200`, virulence divisor `200`, and strength weights `0.5/0.5` are literals in the formulas. Resource profiles are also embedded in the module. The contract says simulation coefficients reside exclusively in `game_balance.py`; the handoff explicitly acknowledges the exception.
- Impact: core host/competition balance cannot be centrally tuned or injected through `BalanceConfig`, contradicting DEC-007 and making isolated interaction tests depend on hidden production constants.
- Recommended action: add named `BalanceConfig` fields/resource profiles and accept an injectable balance in all interaction functions, as the fitness/evolution modules already do. Update tests to use controlled configurations.

### 3. Relation persistence is sequentially idempotent but not conflict-safe by itself

- Severity: medium
- Files: `backend/app/simulation/interactions.py`, `backend/app/models/entities.py`
- Evidence: `persist_parasitism_relation()` performs select-then-insert without locking, upsert or `IntegrityError` recovery. Two transactions establishing the same relation can both observe absence and one will violate the unique constraint.
- Impact: DEC-005's world lock can serialize callers once this is correctly wired into the tick, but the public helper's claimed idempotence depends on an undocumented external lock. DEV/scheduler integration mistakes could abort a whole tick.
- Recommended action: document/enforce that the function requires the world tick lock, or use PostgreSQL upsert/conflict recovery. Add an integration test around the chosen transaction boundary.

### 4. Tests validate pure behavior but omit the critical integration path

- Severity: medium
- Files: `backend/tests/simulation/test_interactions.py`, `backend/tests/simulation/test_service.py`
- Evidence: the ten new tests use `SimpleNamespace` inputs or call persistence directly. No test runs `SimulationService.run_tick()` with competitors or a WILD parasite and host.
- Impact: all new tests pass while the production tick ignores the feature entirely.
- Recommended action: add tests asserting a tick changes fitness under competition, allows WILD parasite establishment, persists exactly one relation over repeated ticks, and penalizes a parasite only when no eligible host exists.

## Confirmed behavior

- Pure competition pressure is bounded, deterministic, ignores extinct/different-habitat/unrelated-resource species and reduces fitness when explicitly passed as context.
- Host compatibility deterministically requires a living, non-parasitic target in the same habitat and incorporates abundance, resistance, trait similarity, mutation and prior contact.
- Parasitism uses only the injected RNG and identical seeds produce identical results.
- WILD status is not excluded by `_alive`; the explicit WILD parasite unit test passes.
- No-host context invokes the centralized fitness penalty and produces fitness below 1 in the tested configuration.
- Sequential calls refresh a single persisted relation rather than duplicating it.

## Validation performed

- `PYTHONPATH=backend python3 -m pytest backend/tests/simulation/test_interactions.py -q` — PASS (`10 passed`).
- `PYTHONPATH=backend python3 -m pytest backend/tests/simulation -q` — PASS (`32 passed`).
- `python3 scripts/task_graph.py validate` — PASS (`GRAPH VALID: 21 tasks`).
- Explicit task scope validation for implementation, test and handoff paths — PASS.
- Static usage search — FAIL integration criterion: interaction hooks have no production caller.

## Files

- `backend/app/simulation/interactions.py`
- `backend/app/simulation/fitness.py`
- `backend/app/simulation/engine.py`
- `backend/app/services/simulation_service.py`
- `backend/app/config/game_balance.py`
- `backend/tests/simulation/test_interactions.py`
- `backend/tests/simulation/test_service.py`
- `agent_reports/mvp-competition-parasitism.md`

## Recommended action

Do not mark this task done or release interaction-dependent tasks. Expand scope or create a mandatory fix task that centralizes all balance constants and wires interactions into the atomic tick, then repeat unit and service-level review. GRAY_BLOOD and bots must not treat the current isolated formulas as a completed ecosystem integration.
