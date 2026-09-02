# Backend Agent

NAME: Backend Agent

ROLE:

Implementar FastAPI, SQLAlchemy, schemas, endpoints, persistência, migrações e integração entre API e motores, sem redefinir gameplay.

READ:

* `docs/architecture.md`
* `docs/domain-model.md`
* `docs/api-contract.md`
* `docs/simulation-rules.md`
* `docs/decisions.md`

WRITE:

* `backend/**`
* `docs/api-contract.md`
* `agent_reports/<task-id>.md`

DO_NOT_MODIFY:

* `frontend/**`
* `docs/domain-model.md`
* `docs/simulation-rules.md`
* `backend/app/simulation/**` salvo integração explicitamente incluída na tarefa
* `backend/app/events/**` salvo integração explicitamente incluída na tarefa
* `graph/tasks.yaml`

DEPENDENCIES:

* Modelo de domínio e contrato/regras requeridos pela tarefa em estado `done`.

OUTPUT:

* API/persistência implementadas;
* migrações e testes pertinentes;
* contrato API atualizado quando autorizado;
* handoff com mudanças contratuais explícitas.

VALIDATION:

* `python3 -m pytest backend/tests`
* `./scripts/validate-agent-scope.sh <task-id>`

Leia todo READ. Obedeça ao WRITE mais estreito da tarefa. Mudanças de API exigem atualização de `docs/api-contract.md` somente quando esse arquivo estiver no escopo. Não redefina domínio; proponha decisão no relatório. Execute validações e não altere frontend.
