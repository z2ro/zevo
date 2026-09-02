# Regras de execução

## Fonte de verdade

`graph/tasks.yaml` é a fonte executável. Ele usa sintaxe JSON, válida em YAML 1.2, para dispensar `yq`/PyYAML. Apenas o Orchestrator altera status ou estrutura do grafo. Prompts definem o teto de autoridade do agente; `write_scope` da tarefa é a restrição efetiva e mais estreita.

## Estados e transições

- `pending`: há dependência diferente de `done`, ou a tarefa ainda não foi promovida.
- `ready`: todas as dependências estão `done` e a tarefa pode iniciar.
- `running`: um agente está executando; o Orchestrator deve registrar ownership antes do disparo.
- `blocked`: falta decisão/entrada externa identificada no handoff.
- `review`: implementação e validação passaram; aguarda Reviewer.
- `failed`: execução, validação ou review falhou. Dependentes permanecem indisponíveis.
- `done`: validação passou e, se `review_required`, existe review `PASS`.

Transições normais: `pending -> ready -> running -> review -> done`. Sem review: `running -> done`. Falha: `running|review -> failed -> ready -> running`. Um bloqueio volta a `ready` quando sua causa é resolvida. Toda transição registra motivo no relatório; somente o Orchestrator edita o grafo.

## Ciclo implement/validate/review

1. Implementador lê contexto e executa a tarefa.
2. Validador de escopo e comandos de `validation` passam.
3. Orchestrator move para `review`.
4. Reviewer cria `agent_reports/<task-id>-review.md` com PASS/FAIL.
5. PASS permite `done`; FAIL leva a `failed` e retorna ao proprietário para correção.
6. A correção repete validação e review. O ciclo ocorre na máquina de estados, não como aresta cíclica no DAG.

## Disponibilidade e bloqueios

Uma dependência só está satisfeita em `done`. `scripts/task_graph.py ready` mostra tarefas executáveis pelo estado atual e também candidatas `pending` cujas dependências terminaram; o Orchestrator deve promovê-las para `ready`. Falha/bloqueio nunca libera dependentes.

## Paralelismo

Tarefas podem rodar juntas somente se: todas as dependências estão `done`; nenhum padrão de `write_scope` pode alcançar o mesmo caminho; não há relação ancestral entre elas; e cada execução usa branch/worktree separado. Na dúvida, serialize. Atualizações de `tasks.yaml`, integração e reviews são serializadas.

Grupos candidatos conhecidos são declarados em `parallel_groups` no próprio grafo. A declaração não libera execução: o Orchestrator ainda deve conferir status efetivo, worktrees e sobreposição semântica dos globs. `python3 scripts/task_graph.py parallel` mostra esses grupos e sua disponibilidade.

Após `domain-model` e `simulation-rules`, `simulation-core`, `event-system-design` e `api-contract` podem avançar em paralelo porque escrevem conjuntos distintos. `frontend` só inicia após `backend-api` e `ui-contract` estarem `done`.

## Falhas

O agente registra comando, saída resumida e causa no handoff. O Orchestrator marca `failed`, impede dependentes e decide entre reutilizar a tarefa ou criar uma tarefa de fix com escopo explícito. Agentes não expandem o próprio escopo.

## Concorrência e Git

O MVP valida alterações visíveis no worktree. Em checkout compartilhado, mudanças simultâneas geram falsa atribuição; por isso paralelismo real requer worktrees Git limpos. Sem Git, use `--files` apenas para validar listas explícitas; execução mutável deve aguardar inicialização do repositório.
