# Handoff — MVP contracts

Task: mvp-contracts  
Agent: Orchestrator Agent  
Status: DONE

## Summary

O MVP foi decomposto em 20 tarefas `mvp-*`. Contratos normativos agora cobrem domínio, tick, evolução, eventos, API e UI. Tarefas críticas exigem review e dependentes só liberam após `done`.

## Files changed

`graph/tasks.yaml`, `scripts/task_graph.py`, `docs/architecture.md`, `docs/domain-model.md`, `docs/simulation-rules.md`, `docs/event-system.md`, `docs/api-contract.md`, `docs/ui-contract.md`, `docs/decisions.md`.

## Contracts changed

API base `/api`; população agregada em um habitat; scheduler no backend; balanceamento central; GRAY_BLOOD aceita parasita WILD; World First único por mundo.

## Tests

`python3 scripts/task_graph.py validate`; `python3 scripts/task_graph.py ready`.

## Failures / Risks

Fórmulas possuem forma normativa, mas valores exatos ficam no objeto central de balanceamento. O índice parcial de uma espécie controlada depende de PostgreSQL. Paralelismo declarado ainda exige worktrees sem sobreposição.

## Notes for next agent

Prontas: `mvp-database-models` e `mvp-frontend-shell`. Backend deve estabelecer modelos/configuração antes do simulation core; frontend pode criar somente shell/tipos até API pronta.
