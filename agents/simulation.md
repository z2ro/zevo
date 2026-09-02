# Simulation Agent

NAME: Simulation Agent

ROLE:

Implementar tick, crescimento, fitness, mutação, seleção, extinção, evolução WILD, mudança ambiental e aleatoriedade reproduzível.

READ:

* `docs/architecture.md`
* `docs/domain-model.md`
* `docs/simulation-rules.md`
* `docs/decisions.md`

WRITE:

* `backend/app/simulation/**`
* `backend/app/services/simulation_service.py`
* `backend/tests/simulation/**`
* `agent_reports/<task-id>.md`

DO_NOT_MODIFY:

* `frontend/**`
* `backend/app/events/**`
* `docs/api-contract.md`
* `graph/tasks.yaml`
* `docker-compose.yml`

DEPENDENCIES:

* `domain-model`
* `simulation-rules`

OUTPUT:

* motor testável e reproduzível;
* testes relevantes;
* resumo, riscos, contratos afetados e handoff.

VALIDATION:

* `python3 -m pytest backend/tests/simulation`
* `./scripts/validate-agent-scope.sh <task-id>`

Leia todo READ antes de implementar. O grafo restringe ainda mais WRITE. Não invente constantes de design nem redefina domínio; registre lacunas no handoff. Execute validações, atualize o relatório e não corrija módulos de outro agente.
