# Registro de decisões

Decisões aceitas só mudam por nova ADR que as substitua. Use o próximo ID sequencial.

## DEC-001 — Simulação independente do frontend

**Data:** 2026-09-02  
**Contexto:** A simulação precisa continuar quando jogadores estão offline.  
**Decisão:** O tick roda no backend independentemente do frontend; o frontend apenas consulta estado e envia comandos.  
**Impacto:** Scheduling, idempotência e persistência são responsabilidades server-side.  
**Status:** Accepted

## DEC-002 — Documentos como contratos compartilhados

**Data:** 2026-09-02  
**Contexto:** Agentes especializados não devem criar contratos incompatíveis.  
**Decisão:** `domain-model.md`, `simulation-rules.md`, `api-contract.md`, `event-system.md` e `ui-contract.md` são memória normativa, com alterações controladas pelo escopo e review.  
**Impacto:** Implementação divergente falha em review; mudanças contratuais aparecem no handoff.  
**Status:** Accepted

## DEC-003 — Um escritor por arquivo durante execução paralela

**Data:** 2026-09-02  
**Contexto:** Tarefas paralelas podem sobrescrever decisões ou código.  
**Decisão:** O Orchestrator só paraleliza tarefas prontas cujos `write_scope` não se sobrepõem; cada tarefa usa branch/worktree própria quando houver Git.  
**Impacto:** Menos conflitos; integração e atualização do grafo permanecem serializadas.  
**Status:** Accepted

## DEC-004 — Grafo em YAML compatível com JSON

**Data:** 2026-09-02  
**Contexto:** O ambiente inicial não possui `yq` nem dependências Python instaladas.  
**Decisão:** `graph/tasks.yaml` usa sintaxe JSON, que é YAML 1.2 válido, permitindo leitura pela biblioteca padrão do Python.  
**Impacto:** Scripts são autossuficientes; comentários dentro do grafo não são suportados.  
**Status:** Accepted

## DEC-005 — Monólito modular e scheduler no backend

**Data:** 2026-09-02  
**Contexto:** O MVP precisa persistir e simular sem microserviços.  
**Decisão:** FastAPI hospeda API e um scheduler de tick; execução usa lock transacional por mundo. DEV simulate usa o mesmo serviço/lock.  
**Impacto:** Deploy simples; múltiplas réplicas exigirão coordenação adicional.  
**Status:** Accepted

## DEC-006 — População única por espécie no MVP

**Data:** 2026-09-02  
**Contexto:** Subpopulações completas ampliariam banco, API e UI.  
**Decisão:** Uma espécie ocupa um habitat; split aplica efeito fundador à população agregada e migração move a fração sobrevivente.  
**Impacto:** Prova decisões e deriva, mas não mantém colônias simultâneas.  
**Status:** Accepted

## DEC-007 — Balanceamento em configuração Python

**Data:** 2026-09-02  
**Contexto:** Fórmulas ajustáveis não podem espalhar números mágicos.  
**Decisão:** Coeficientes, bootstrap, limiares, bots e eventos residem em `backend/app/config/game_balance.py`; env cobre operação/seed/DEV.  
**Impacto:** Testes podem injetar configuração e RNG reproduzível.  
**Status:** Accepted
