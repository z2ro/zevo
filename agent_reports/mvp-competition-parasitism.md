# Task

`mvp-competition-parasitism`

# Agent

Simulation Agent

# Status

PASS — implemented and validated; awaiting Reviewer.

# Summary

Added pure, deterministic competition/resource-overlap and host-compatibility/parasitism rules. Added a fitness-context integration hook and idempotent persistence of established parasitism relations. WILD parasites follow the same eligibility rules as controlled species.

# Files changed

- `backend/app/simulation/interactions.py`
- `backend/tests/simulation/test_interactions.py`
- `agent_reports/mvp-competition-parasitism.md`

# Contracts changed

None. The implementation follows the existing domain model and simulation contract.

# Tests

- `python3 -m pytest backend/tests/simulation/test_interactions.py -q`
- `python3 -m pytest backend/tests/simulation -q`
- `./scripts/validate-agent-scope.sh mvp-competition-parasitism --files backend/app/simulation/interactions.py backend/tests/simulation/test_interactions.py agent_reports/mvp-competition-parasitism.md`

# Failures

None. Interaction tests: 10 passed. Full simulation suite: 32 passed. Scope validation: PASS.

# Risks

- Interaction coefficients that were absent from `BalanceConfig` are named and centralized inside the pure interaction formulas because this task cannot modify configuration. A future balance task should move resource profiles and host score weights into `game_balance.py`.
- The simulation service/engine must call `fitness_context_for` and `persist_parasitism_relation`; those files are outside this task's write scope.

# Notes for next agent

- Tick integration should build one habitat-local living-species tuple, call `fitness_context_for` for each species, then evaluate/persist parasite-host relations with the tick-derived RNG.
- Event Engine can consume persisted `SpeciesRelation` fields without duplicating compatibility rules.
