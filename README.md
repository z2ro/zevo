# Zevo

Jogo persistente de evolução de espécies. Neste estágio, o repositório contém somente o scaffolding de desenvolvimento multiagente; features grandes do jogo ainda não foram implementadas.

## Multi-Agent Development

### Por que existe

O projeto separa contexto, propriedade de arquivos e contratos para que agentes Codex especializados trabalhem sem redefinir regras ou sobrescrever módulos vizinhos. O DAG em `graph/tasks.yaml` controla precedência; `docs/` funciona como memória normativa; `agent_reports/` preserva handoffs e reviews fora do chat.

### Agentes disponíveis

| Agente | Responsabilidade | Escrita principal |
|---|---|---|
| `orchestrator` | estado, dependências, bloqueios, ADRs e despacho | grafo, arquitetura, decisões |
| `game-design` | domínio e regras de gameplay | domain model e simulation rules |
| `simulation` | tick e evolução reproduzível | simulation e seus testes |
| `backend` | FastAPI, SQLAlchemy, persistence, migrations e API | backend e contrato API quando autorizado |
| `frontend` | React/TypeScript, UX e consumo da API | frontend e contrato UI |
| `events` | condições, consequências, World First e histórico | event engine, testes e documentação de eventos |
| `tests` | testes e diagnóstico, sem features | diretórios de testes |
| `reviewer` | revisão independente PASS/FAIL | relatório de review apenas |

Cada prompt em `agents/*.md` declara `NAME`, `ROLE`, `READ`, `WRITE`, `DO_NOT_MODIFY`, `DEPENDENCIES`, `OUTPUT` e `VALIDATION`. O `write_scope` da tarefa sempre reduz — nunca amplia — o escopo geral do agente.

### Grafo inicial

```text
domain-model
└── simulation-rules
    ├── simulation-core ─┬── event-engine ─┐
    │                    └── backend-api ◄──┤
    ├── event-system-design ────────────────┘
    └── api-contract ─────┬── backend-api
                         └── ui-contract

backend-api + ui-contract ──> frontend
simulation-core + event-engine + backend-api + frontend ──> tests
tests + frontend ──> final-review
```

Após `domain-model` e `simulation-rules`, `simulation-core`, `event-system-design` e `api-contract` podem ser executadas em paralelo em worktrees separadas. O Orchestrator deve sempre confirmar que `write_scope` não se sobrepõe. `frontend` aguarda `backend-api` e `ui-contract` concluídas.

Estados suportados: `pending`, `ready`, `running`, `blocked`, `review`, `failed` e `done`. Dependências só são satisfeitas por `done`. Veja todas as transições, política de falha e paralelismo em `graph/execution-rules.md`.

### Preparação

Os scripts exigem Bash, Python 3, Git e Codex CLI. Não há credenciais no repositório; autentique o CLI pelo mecanismo da sua instalação. Este workspace inicial não possui um `.git` funcional. Em um clone normal, faça o commit do scaffolding antes de uma execução mutável; aqui, use os modos `--dry-run`/`--files` para inspeção até o Git ser inicializado externamente.

O launcher usa `codex exec --sandbox workspace-write -C <repo> -`: o prompt é enviado por stdin e o agente começa na raiz. Essa forma segue a referência oficial do Codex CLI para execução não interativa, diretório e sandbox.

### Ver tarefas disponíveis

```bash
./scripts/run-task.sh --list-ready
python3 scripts/task_graph.py validate
python3 scripts/task_graph.py parallel
```

O primeiro comando distingue tarefas `ready` de candidatas `pending` que o Orchestrator deve promover. Apenas o Orchestrator edita estados no YAML.

### Executar uma tarefa

Inspecione o envelope sem chamar Codex:

```bash
./scripts/run-task.sh domain-model --dry-run
```

Em um worktree Git limpo, execute:

```bash
./scripts/run-task.sh domain-model
```

O script valida o grafo e dependências, mostra contexto/escopo, monta o prompt especializado, chama Codex, verifica alterações e executa validações. Ele não muda status automaticamente: o Orchestrator registra `running`, `review`, `failed` ou `done` de forma serializada.

Para invocar um papel fora de uma tarefa (preferencialmente diagnóstico):

```bash
./scripts/run-agent.sh orchestrator --dry-run "Liste bloqueios atuais"
```

### Executar review

Depois de validação e de o Orchestrator mover a tarefa para `review`:

```bash
./scripts/run-task.sh domain-model --review
```

O Reviewer só pode escrever `agent_reports/domain-model-review.md`, usando `status`, `severity`, `issues`, `files` e `recommended_action`. `PASS` permite `done`; `FAIL` leva a `failed`, correção pelo agente proprietário, nova validação e novo review. Para a revisão integrada, promova e execute:

```bash
./scripts/run-task.sh final-review --review
```

### Detectar alteração fora de escopo

Em Git, o validador combina mudanças staged, unstaged e untracked:

```bash
./scripts/validate-agent-scope.sh simulation-core
```

Teste explícito positivo e negativo, mesmo antes de haver Git:

```bash
./scripts/validate-agent-scope.sh simulation-core --files backend/app/simulation/core.py
./scripts/validate-agent-scope.sh simulation-core --files frontend/src/App.tsx
```

O segundo comando retorna código `3` e lista o arquivo proibido. Ausência de worktree Git retorna `4`. Em worktree sujo, alterações anteriores também aparecem; o runner recusa esse estado por padrão. Para paralelismo real, use uma branch/worktree limpa por tarefa.

### Handoff

Copie `agent_reports/TEMPLATE.md` para `agent_reports/<task-id>.md`. Preencha Task, Agent, Status, Summary, Files changed, Contracts changed, Tests executed, Failures, Open questions e Next agent notes. Reviews usam o template separado e nunca sobrescrevem o relatório original.

### Adicionar um agente

1. Crie `agents/<nome>.md` com todos os oito campos obrigatórios.
2. Dê ownership estreito, READ suficiente e proibições explícitas.
3. Inclua o relatório da tarefa em WRITE, mas não conceda escrita no grafo.
4. Rode `python3 scripts/task_graph.py validate` depois que alguma tarefa referenciá-lo.

### Adicionar uma tarefa

1. Adicione uma entrada a `graph/tasks.yaml` com `id` e os oito campos operacionais obrigatórios.
2. Use ID `kebab-case`, dependências existentes, arquivos de contexto existentes e globs relativos.
3. Garanta que o escopo seja subconjunto do WRITE do agente e inclua `agent_reports/<id>.md`.
4. Evite sobreposição com tarefas paralelas; represente precedência em `depends_on`.
5. Defina `review_required` e comandos de validação confiáveis.
6. Valide e confira disponibilidade:

```bash
python3 scripts/task_graph.py validate
./scripts/run-task.sh --list-ready
```

### Self-test da infraestrutura

```bash
./scripts/test-multi-agent.sh
```

O teste verifica o grafo, tarefa inicial, dry-run, escopo permitido/proibido, bloqueio por dependência e sintaxe dos scripts. Testes do produto só existirão quando as respectivas tarefas os implementarem.

### Limitações do MVP

- O grafo é atualizado manualmente pelo Orchestrator; ainda não há lock/daemon de scheduling.
- `tasks.yaml` usa o subconjunto JSON de YAML para não depender de `yq`/PyYAML.
- A validação Git atribui todas as mudanças visíveis à execução; paralelismo seguro requer worktrees.
- Globs protegem por convenção e pós-validação, não formam uma sandbox por agente.
- Comandos de `validation` são código confiável versionado e executados com `bash -lc`; mudanças neles exigem review.
- O jogo, banco, containers e pipelines ainda serão criados pelas tarefas do DAG.
