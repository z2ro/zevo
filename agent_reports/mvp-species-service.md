# Handoff — mvp-species-service

**Task:** mvp-species-service  
**Agent:** Backend Agent  
**Status:** review

## Summary

Implementados schemas Pydantic estritos para traits, criação, preview e leitura de espécie, além do serviço de preview, criação e abandono. A criação bloqueia o Player em PostgreSQL, verifica a invariante de espécie controlada e também depende do índice único parcial como proteção final contra corrida. O abandono preserva a espécie e seu creator, alterando-a para WILD.

## Files changed

- `backend/app/schemas/species.py`
- `backend/app/services/species_service.py`
- `backend/tests/services/test_species_service.py`
- `agent_reports/mvp-species-service.md`

## Contracts changed

Nenhum. A implementação segue `docs/api-contract.md`: schemas snake_case, preview sem componentes internos e erros de serviço serializáveis como `{"error": ...}`.

## Tests

- `python3 -m pytest backend/tests/services/test_species_service.py -q` — 8 passed.

## Failures

Nenhuma.

## Risks

- A futura camada FastAPI deve converter `SpeciesServiceError.status_code` e `as_error()` diretamente em resposta HTTP.
- O serviço faz `flush`, mas deixa `commit` sob responsabilidade da unidade de trabalho/rota. Em conflito de integridade ele executa rollback para restaurar a Session.
- Logs de `species_created` e `species_abandoned` pertencem à tarefa de integração da API/observabilidade.

## Notes for next agent

- Use `SpeciesCreate` tanto em `/preview` quanto em `/species` para manter validações idênticas.
- `preview_species`, `create_species` e `abandon_species` são os pontos de integração públicos.
- Não replique o cálculo de fitness nas rotas; o serviço já reutiliza `simulation.preview_fitness`.
