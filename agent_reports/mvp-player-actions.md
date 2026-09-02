# Task

`mvp-player-actions`

# Agent

Simulation Agent

# Status

FIXED — review findings addressed and task validation passed; ready for re-review.

# Summary

Implemented player action domain primitives and a transactional service for pending migration/completion, aggregate split with deterministic founder effect and persisted trait history, immediate strategy changes with tick-based cooldown, and mutually exclusive temporary reproduction/survival focuses. All commands enforce ownership of the current ACTIVE controlled species.

The review correction guarantees one or two actual founder changes for valid species even when all traits are zero or a trait is at 100/the total budget, and centralizes all five adjustable action coefficients in `BalanceConfig`.

# Files changed

- `backend/app/simulation/actions.py`
- `backend/app/config/game_balance.py` (explicit Orchestrator scope expansion)
- `backend/app/services/action_service.py`
- `backend/tests/simulation/test_actions.py`
- `agent_reports/mvp-player-actions.md`

# Contracts changed

None. The implementation follows the published API and DEC-006 single-population model.

# Tests

- `python3 -m pytest backend/tests/simulation/test_actions.py -q` — `10 passed`
- `python3 -m compileall -q backend/app/services/action_service.py backend/app/simulation/actions.py` — passed
- Full simulation suite — `35 passed`

# Failures

No test failures. Scope validation is temporarily blocked by a graph-level validation error: parallel group `core-features` now contains identical `backend/app/config/game_balance.py` scopes. This graph reconciliation belongs to the Orchestrator.

# Risks

- Migration/focus processors are explicit functions. The simulation integration owner must call `complete_due_migrations` and `complete_due_focuses` at tick boundaries and consume `active_focus_modifiers` during population calculation.
- In the one-population MVP, migration replaces the aggregate population with the migrating survivors, as required by DEC-006; no source colony remains.

# Notes for next agent

- API endpoints should translate `ActionServiceError` and return the persisted `PlayerAction` for 202 commands.
- Scheduler should process due migration before interaction/fitness calculation, ensuring the species participates in its destination habitat during that tick.
- Apply focus modifiers once in population birth/death calculation; do not mutate base traits for temporary focus.
- Bot actions can call the same functions and remain subject to the same ownership/status checks.
