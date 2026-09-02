# Handoff: mvp-event-db-constraints

Task: `mvp-event-db-constraints`  
Agent: Backend Agent  
Status: REVIEW

## Summary

`GameEvent` agora materializa `idempotency_key` e `repeat_scope`, permitindo que PostgreSQL/SQLite rejeitem atomicamente eventos duplicados por chave e pelas políticas uma vez por mundo, espécie ou jogador.

## Files changed

- `backend/app/models/entities.py`
- `backend/alembic/versions/0002_event_uniqueness.py`
- `backend/tests/models/test_event_constraints.py`
- `agent_reports/mvp-event-db-constraints.md`

## Contracts changed

Nenhum contrato externo. O schema passa a cumprir a garantia já publicada em `docs/event-system.md`.

## Tests

- `python3 -m pytest backend/tests/models/test_event_constraints.py -q`
- Resultado: `9 passed`; inclui compilação DDL no dialect PostgreSQL e execução das constraints no SQLite.
- `python3 scripts/task_graph.py validate`
- validação explícita de escopo nos quatro arquivos.

## Failures

Nenhuma conhecida.

## Risks

- O Event Engine precisa preencher as novas colunas; enquanto não o fizer, eventos `ALWAYS` continuam válidos, mas as novas garantias de política não são acionadas.
- O ciclo real Alembic/PostgreSQL permanece responsabilidade da integração Docker, pois Alembic não está instalado no host atual.

## Notes for next agent

- Mapear `RepeatPolicy`: `ALWAYS`, `WORLD`, `SPECIES`, `PLAYER` em `repeat_scope`.
- Persistir a chave também em `idempotency_key`; metadata pode mantê-la apenas para compatibilidade/auditoria.
- Tratar `IntegrityError` como duplicação e reler após finalizar/renovar a transação concorrente.
