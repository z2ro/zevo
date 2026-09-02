# Review — mvp-simulation-core

status: PASS

severity: none

## Issues

Nenhuma pendência encontrada na reavaliação.

## Verificação das correções anteriores

1. **Isolamento multiworld — corrigido.** A consulta restringe `Habitat.world_id`; teste com dois mundos confirma que somente o mundo solicitado avança.
2. **Limite populacional — corrigido.** A pressão de capacidade é suave e o delta respeita ±35%, inclusive acima de `K`; há regressão específica.
3. **Balance injetado — corrigido.** `attempt_mutation` propaga `balance` ao fitness anterior e posterior; o teste com `fitness_max` customizado passa.
4. **Centralização — corrigida.** Coeficientes ajustáveis residem em `BalanceConfig`, e `game_balance.py` foi adicionado ao `write_scope` da tarefa.
5. **Consistência do snapshot — corrigida.** Fitness pós-mutação é persistido com os traits pós-mutação; há teste dedicado.
6. **Grafo — reconciliado.** `mvp-database-models` está `done`; `mvp-simulation-core` permanece `failed` até o Orchestrator consumir este PASS.

## Checks executados

- `python3 -m pytest backend/tests/simulation -q` — **15 passed**.
- `python3 -m compileall -q backend/app/simulation backend/app/services/simulation_service.py` — **passed**.
- `python3 scripts/task_graph.py validate` — **GRAPH VALID: 21 tasks**.
- Validação explícita dos cinco caminhos representativos via `validate-agent-scope.sh` — **PASS**.

## Files revisados

- `backend/app/config/game_balance.py`
- `backend/app/simulation/*.py`
- `backend/app/services/simulation_service.py`
- `backend/tests/simulation/*.py`
- contratos relevantes, grafo e handoff da tarefa

## Recommended action

Orchestrator deve marcar `mvp-simulation-core` como `done` e liberar `mvp-species-service`. Teste de contenção real no PostgreSQL permanece para a integração e não bloqueia esta entrega.
