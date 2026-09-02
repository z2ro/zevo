# Handoff — mvp-frontend-shell

Task: mvp-frontend-shell  
Agent: Frontend Agent  
Status: DONE

## Summary

Shell Vite/React/TypeScript com navegação para todas as rotas do MVP, cliente HTTP tipado, operações da API oficial, polling consciente da visibilidade da aba e estados loading/error/empty/success reutilizáveis. As rotas usam placeholders intencionais; páginas finais pertencem às tarefas posteriores.

## Files changed

- `frontend/package.json`, TypeScript/Vite config e `index.html`
- `frontend/src/main.tsx`, `styles.css`
- `frontend/src/app/**`, `frontend/src/api/**`, `frontend/src/types/**`
- `frontend/package-lock.json` (gerado pela instalação)
- `agent_reports/mvp-frontend-shell.md`

## Contracts changed

Nenhum. A implementação segue `docs/api-contract.md` e `docs/ui-contract.md`.

## Tests

- `npm --prefix frontend run build`
- `./scripts/validate-agent-scope.sh mvp-frontend-shell --files <19 arquivos alterados>` — PASS

## Failures

- Validação automática via `git diff` indisponível porque o workspace não é um worktree Git; a lista explícita de 19 arquivos passou.

## Risks

- Tipos refletem o contrato documental; devem ser ajustados via handoff se a implementação backend divergir.
- `Legacy` pressupõe nomes agregados naturais ainda não detalhados campo a campo no contrato.

## Notes for next agent

Substituir os `PlaceholderPage` por páginas dentro do escopo das tarefas correspondentes. Reutilizar `gameApi`, `AsyncState` e `usePolling`; manter polling cancelado ao desmontar e pausado quando a aba está oculta.
