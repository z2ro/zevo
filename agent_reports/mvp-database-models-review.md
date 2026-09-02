# Review: mvp-database-models — Fix cycle 1

status: PASS

severity: none

## Scope reviewed

- Task: `mvp-database-models`
- Agent: Backend Agent
- Contracts: `docs/architecture.md`, `docs/domain-model.md`, `docs/decisions.md`
- Implementation: configuration, SQLAlchemy models/session, bootstrap and Alembic baseline
- Tests: `backend/tests/models/**`
- Handoff: `agent_reports/mvp-database-models.md`

## Resolution of previous issues

1. **PostgreSQL boolean constraints — RESOLVED.** Both ORM metadata and frozen migration now use `IS FALSE`; PostgreSQL DDL compilation no longer contains `is_player_controlled = 0`.
2. **Missing validation suite — RESOLVED.** The declared command passes with six tests covering bootstrap, concurrent bootstrap, PostgreSQL DDL portability, controlled-species uniqueness, global historical-flag uniqueness and migration immutability.
3. **Mutable metadata-driven migration — RESOLVED.** Revision `0001_initial_schema` uses explicit Alembic create/drop operations and does not import or invoke `Base.metadata`.
4. **Bootstrap concurrency — RESOLVED for the supported MVP topology.** PostgreSQL initializers acquire a transaction advisory lock; in-process calls are serialized for SQLite/tests, with defensive integrity-conflict recovery.
5. **Historical flag uniqueness with nullable subjects — RESOLVED.** Separate partial unique indexes cover global, species and player subjects; a check constraint prevents a flag from addressing species and player simultaneously.

## Issues

None blocking.

## Files

- `backend/app/models/entities.py`
- `backend/app/models/enums.py`
- `backend/app/db/bootstrap.py`
- `backend/app/db/session.py`
- `backend/app/config/settings.py`
- `backend/app/config/game_balance.py`
- `backend/alembic/env.py`
- `backend/alembic/versions/0001_initial_schema.py`
- `backend/tests/models/conftest.py`
- `backend/tests/models/test_models.py`
- `backend/tests/models/test_bootstrap_concurrency.py`
- `agent_reports/mvp-database-models.md`

## Validation performed

- `PYTHONPATH=backend python3 -m pytest backend/tests/models -q` — PASS (`6 passed`).
- `PYTHONPATH=backend python3 -m compileall -q backend/app backend/alembic` — PASS.
- `python3 scripts/task_graph.py validate` — PASS (`GRAPH VALID: 21 tasks`).
- Explicit scope validation for the seven fix-cycle paths — PASS.
- PostgreSQL DDL portability is exercised by the model test and passed.

## Non-blocking limitations

- A real PostgreSQL `upgrade -> downgrade -> upgrade` cycle was not executable in this review environment: no PostgreSQL Compose service/configuration exists yet and the available standalone Alembic executable runs Python 3.10, while the project uses `StrEnum` (Python 3.11+). The Docker/integration task must exercise this against the target runtime before final MVP approval.
- Cross-process bootstrap safety outside PostgreSQL is not guaranteed. This does not affect the declared PostgreSQL deployment; SQLite remains a local test adapter.
- Service-level transaction handling and HTTP 409 mapping for the one-controlled-species constraint belong to subsequent backend service/API tasks.

## Recommended action

Mark `mvp-database-models` as `done` and release its dependents. Preserve the PostgreSQL migration-cycle check as a mandatory validation for `mvp-docker` or final integration review.
