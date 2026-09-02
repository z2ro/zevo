# Review — mvp-event-engine

status: FAIL

severity: high

## Summary

A engine apresenta boa separação entre definição, avaliação e persistência; as condições `All`, `Any` e `Not` são composáveis, o evaluator não contém regras narrativas e o savepoint cobre corretamente o evento e efeitos ORM que permaneçam na transação do chamador. Entretanto, as garantias de idempotência documentadas não são asseguradas pelo banco em todos os modos suportados. O check-then-insert atual permite duplicações concorrentes, inclusive para políticas de repetição que a API apresenta como `ONCE_*`.

## Issues

### EVT-REV-001 — Idempotency key de eventos repetíveis não é protegida contra concorrência

- severity: high
- files: `backend/app/events/service.py`, `backend/app/models/entities.py`, `backend/alembic/versions/0001_initial_schema.py`, `docs/event-system.md`
- evidence: `_find_duplicate()` percorre JSON para localizar `_idempotency_key`, mas `game_events` não possui coluna/index/constraint único para essa chave. Duas transações podem observar ausência e inserir o mesmo evento. O `IntegrityError` tratado pelo serviço não ocorrerá nesse caso.
- contract impact: `docs/event-system.md` afirma que constraints impedem duplicação por idempotency key; a implementação não satisfaz essa afirmação.
- recommended_action: persistir a chave em coluna própria e criar unicidade adequada, por exemplo `(world_id, code, idempotency_key)` quando não nula; adicionar teste concorrente em PostgreSQL ou teste de integração equivalente.

### EVT-REV-002 — `ONCE_PER_SPECIES` e `ONCE_PER_PLAYER` não possuem unicidade no banco

- severity: high
- files: `backend/app/events/service.py`, `backend/app/models/entities.py`, `backend/alembic/versions/0001_initial_schema.py`
- evidence: somente eventos com `global_unique = true` possuem índice parcial único `(world_id, code)`. As políticas por espécie e por jogador fazem consulta prévia, mas inserem linhas sem constraint distinta; sob concorrência ambas podem persistir duplicatas.
- recommended_action: materializar o escopo/política de repetição no schema ou criar índices parciais/constraints que garantam `(world_id, code, species_id)` e `(world_id, code, player_id)` para os respectivos eventos. Cobrir corridas concorrentes.

### EVT-REV-003 — Cobertura valida apenas repetição sequencial

- severity: medium
- files: `backend/tests/events/test_engine.py`
- evidence: os testes de idempotência e `RepeatPolicy` fazem duas chamadas na mesma sessão, sequencialmente. Não exercitam duas sessões/transações nem demonstram que a constraint absorve a corrida.
- recommended_action: adicionar testes com sessões independentes sobre PostgreSQL para idempotency key e políticas `ONCE_PER_*`. Manter os testes unitários atuais para a semântica sequencial.

### EVT-REV-004 — Estado do grafo não corresponde ao handoff/review

- severity: low
- files: `graph/tasks.yaml`, `agent_reports/mvp-event-engine.md`
- evidence: o handoff declara `Status: REVIEW`, enquanto `python3 scripts/task_graph.py task mvp-event-engine` retorna `status: ready`. Pelas regras, o Reviewer deveria receber uma tarefa em `review` após validação.
- recommended_action: Orchestrator deve alinhar a transição no grafo antes de reencaminhar a correção para novo review.

## Positive findings

- Condições compostas e paths pontilhados estão desacoplados de regras específicas como GRAY_BLOOD.
- `RandomRoll` usa o PRNG fornecido pelo contexto e limita chance DEV a 1.0.
- O evento é flushado antes das consequências e ambos ficam dentro de `begin_nested()`, permitindo rollback de alterações ORM quando uma consequência falha, desde que callbacks não façam commit/IO externo.
- A constraint de evento global único oferece proteção real para World Firsts por mundo.
- Historical flags possuem índices únicos por escopo global, espécie e jogador.
- Não há branch narrativo gigante ou acoplamento ao frontend/simulation loop neste módulo.

## Validation

- `python3 -m pytest backend/tests/events/test_engine.py -q` — PASS, 12 passed.
- `python3 scripts/task_graph.py validate` — PASS, 21 tasks.
- `./scripts/validate-agent-scope.sh mvp-event-engine --files backend/app/events/core.py backend/app/events/conditions.py backend/app/events/service.py backend/tests/events/test_engine.py agent_reports/mvp-event-engine.md` — PASS, 5 paths.
- A validação Git automática não pôde ser usada porque o workspace não é um worktree Git; foi usada a lista explícita de arquivos do handoff.

## Recommended action

Retornar a tarefa ao Event Engine Agent em uma tarefa de correção coordenada com Backend Agent, pois a correção exige mudança de schema/migration fora do `write_scope` atual de `mvp-event-engine`. Após implementar constraints e testes concorrentes, repetir validação e review.
