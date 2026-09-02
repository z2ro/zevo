# Review: mvp-species-service

status: PASS

severity: low

## Scope reviewed

- Task: `mvp-species-service`
- Agent: Backend Agent
- Contracts: `docs/domain-model.md`, `docs/api-contract.md`, `docs/simulation-rules.md`, `docs/decisions.md`
- Implementation: `backend/app/schemas/species.py`, `backend/app/services/species_service.py`
- Tests: `backend/tests/services/test_species_service.py`
- Handoff: `agent_reports/mvp-species-service.md`

## Issues

### 1. Integrity errors are translated too broadly

- Severity: low
- Files: `backend/app/services/species_service.py`
- Evidence: every `IntegrityError` raised by `session.flush()` during creation is converted to `controlled_species_exists`/409.
- Impact: the expected concurrent unique-index race is handled correctly, but an unrelated database failure such as a concurrent habitat deletion/foreign-key failure would be reported with a misleading error code.
- Recommended action: in a future hardening task, identify the violated constraint (or re-query after rollback) and translate only `uq_species_one_controlled_per_player` to this conflict; allow unexpected integrity failures to surface as infrastructure errors.

### 2. Concurrent creation behavior is verified only indirectly by the committed suite

- Severity: low
- Files: `backend/tests/services/test_species_service.py`
- Evidence: the suite tests the sequential guard and the model suite tests the partial index, but this task's committed tests do not run two independent creation sessions concurrently.
- Impact: the intended player-row-lock plus unique-index behavior could regress without a direct service-level test.
- Recommended action: add a PostgreSQL integration test for concurrent creation in `mvp-integration-tests`; SQLite cannot validate `SELECT ... FOR UPDATE` semantics.

## Verified behavior

- Trait fields are bounded to `[0,100]`; weighted cost is centralized in `BALANCE.trait_costs`; cost 100 is accepted and cost 101 is rejected.
- Parasitic type, `PARASITIC` energy and `PARASITE` strategy must appear together, preventing host-dependent modes from being selected independently.
- Preview and creation share `SpeciesCreate`, and both delegate fitness to `app.simulation.fitness.preview_fitness`; no duplicate fitness formula was introduced.
- Creation locks the player on PostgreSQL, checks the current controlled species, and retains the database partial unique index as the final concurrency guard.
- Canonical initial population and state are applied, and created fitness equals the public preview for the same habitat/payload.
- Abandonment is limited to the player's current ACTIVE species, changes it to WILD, clears control and preserves creator/population/history identity, allowing a successor species.
- Service errors carry API-compatible status, code, message and details.

## Files

- `backend/app/schemas/species.py`
- `backend/app/services/species_service.py`
- `backend/tests/services/test_species_service.py`
- `backend/app/simulation/fitness.py`
- `backend/app/models/entities.py`
- `agent_reports/mvp-species-service.md`

## Validation performed

- `PYTHONPATH=backend python3 -m pytest backend/tests/services/test_species_service.py -q` — PASS (`8 passed`).
- `PYTHONPATH=backend python3 -m pytest backend/tests/models backend/tests/simulation backend/tests/services/test_species_service.py -q` — PASS (`29 passed`).
- Additional two-session SQLite creation race — PASS: exactly one creation succeeded, the loser received `controlled_species_exists`/409, and one controlled species remained.
- `python3 scripts/task_graph.py validate` — PASS (`GRAPH VALID: 21 tasks`).
- Explicit task scope validation for four changed paths — PASS.

## Recommended action

Mark `mvp-species-service` as `done` and release dependent action/API tasks. Carry the two low-severity hardening items into PostgreSQL integration coverage; neither blocks the documented MVP behavior.
