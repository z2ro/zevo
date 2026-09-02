# Handoff: mvp-database-models

Task: `mvp-database-models`  
Agent: Backend Agent  
Status: REVIEW (FIX CYCLE 1)

## Summary

Implementada a fundação persistente do MVP: configuração operacional por ambiente, balanceamento central, engine/session SQLAlchemy, bootstrap idempotente de Eos-1, cinco habitats, Zero e cinco bots, modelos persistentes e migration inicial Alembic.

## Files changed

- `backend/app/config/__init__.py`
- `backend/app/config/settings.py`
- `backend/app/config/game_balance.py`
- `backend/app/db/__init__.py`
- `backend/app/db/base.py`
- `backend/app/db/session.py`
- `backend/app/db/bootstrap.py`
- `backend/app/models/__init__.py`
- `backend/app/models/enums.py`
- `backend/app/models/entities.py`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_initial_schema.py`
- `agent_reports/mvp-database-models.md`

## Contracts changed

Nenhum. A implementação segue `docs/domain-model.md` e DEC-005/006/007.

## Tests

- `PYTHONPATH=backend python3 -m compileall -q backend/app backend/alembic` — PASS.
- Smoke SQLite in-memory com `Base.metadata.create_all`, bootstrap repetido, 1 mundo, 5 habitats e 6 players — PASS (11 tabelas).
- `python3 scripts/task_graph.py validate` — PASS (`GRAPH VALID: 21 tasks`).
- Fix cycle: `PYTHONPATH=backend python3 -m pytest backend/tests/models -q` — PASS (`6 passed`).
- PostgreSQL dialect compilation asserts portable `IS FALSE` constraints — PASS.
- SQLite file-backed concurrent bootstrap with two sessions — PASS.
- Frozen migration regression check (explicit `op.create_table`, no live `Base.metadata`) — PASS.
- Fix-cycle scope validation — PASS (7 paths).

## Fix cycle 1

- Corrigidas constraints booleanas para SQL portável PostgreSQL (`IS FALSE`).
- Migration `0001` congelada com operações Alembic explícitas; removido acoplamento a metadata ORM viva.
- Flags históricas globais, por espécie e por player agora possuem índices parciais únicos; uma constraint impede subject duplo ambíguo.
- Bootstrap serializa threads no processo e usa `pg_advisory_xact_lock` no PostgreSQL, com recuperação defensiva de conflito.
- Adicionados seis testes focados de models, DDL, invariantes, migration e bootstrap concorrente.

## Failures

- Nenhuma na validação declarada.
- Alembic e um PostgreSQL executável não estão disponíveis no ambiente host desta tarefa; o ciclo real `upgrade/downgrade/upgrade` deve ser confirmado pela tarefa Docker/integration. A estrutura PostgreSQL foi validada por compilação do dialect SQLAlchemy.

## Risks

- A migration inicial é explícita e imutável. Mudanças futuras exigem novas revisions.
- O índice parcial garante uma espécie controlada por criador em PostgreSQL e SQLite. A camada de serviço ainda deve serializar criação/abandono e converter conflito em HTTP 409.
- O advisory lock usa uma chave fixa reservada ao bootstrap; outros inicializadores devem manter a mesma convenção.

## Notes for next agent

- Importe enums e entidades de `app.models`.
- Use `create_engine_for_url("sqlite+pysqlite:///:memory:")` em testes.
- Chame `bootstrap_world(session)` após migrations; a operação é idempotente.
- `event_metadata`/`flag_metadata` são os atributos Python que mapeiam para a coluna SQL `metadata`, evitando colisão com `Base.metadata`.
