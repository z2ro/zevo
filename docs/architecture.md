# Arquitetura

## Visão geral

Zevo é um jogo persistente de evolução no qual cada jogador controla uma espécie ativa e espécies legadas continuam no mundo sob controle autônomo. O MVP é um monólito modular: FastAPI hospeda API e scheduler; PostgreSQL é canônico; React usa polling.

## Stack prevista

- Backend: Python, FastAPI, SQLAlchemy, PostgreSQL e Alembic.
- Frontend: React, TypeScript e Vite.
- Infraestrutura: Docker e Docker Compose.
- Qualidade: testes unitários e de integração, logs estruturados e métricas operacionais.

## Módulos e responsabilidades

- `backend/app/simulation/`: motor puro do passo de simulação, regras determinísticas e aleatoriedade injetada.
- `backend/app/events/`: definições, avaliação e consequências de eventos.
- `backend/app/services/`: casos de uso e fronteiras transacionais.
- backend restante: API, modelos persistentes, schemas e migrações.
- `frontend/`: interface e consumo exclusivo do contrato publicado.
- `docs/`: contratos e memória compartilhada; decisões normativas prevalecem sobre suposições locais.
- `graph/`: estado e dependências do trabalho.
- `agent_reports/`: handoffs persistentes por tarefa.

## Dependências e contratos

O modelo de domínio e as regras de simulação alimentam simulation e events. A API integra persistence e simulation, mas publica apenas o contrato de `docs/api-contract.md`. O frontend depende desse contrato, nunca de modelos SQLAlchemy. Mudanças incompatíveis exigem tarefa explícita, atualização documental e revisão dos consumidores.

## Fluxo de execução

Uma requisição HTTP entra no FastAPI, é validada por um schema, chama um serviço de aplicação e encerra uma transação. O serviço pode consultar o motor de simulação ou o motor de eventos. O frontend apenas envia comandos e renderiza projeções retornadas pela API.

## Persistência

PostgreSQL é a fonte de verdade e usa volume Compose. SQLAlchemy delimita transações; Alembic roda upgrade no startup antes da API e bootstrap idempotente cria Eos-1. Eventos usam o passo interno para idempotência. O backend aguarda healthcheck do banco; frontend é servido na porta 5173.

## Passo de simulação

O scheduler/backend solicita um passo independentemente do frontend. A idade planetária deriva do tempo real decorrido; gerações avançam individualmente para espécies vivas. Em uma única unidade lógica: carrega snapshot, aplica pressão ambiental, crescimento, relações, seleção, mutação/extinção, comportamento WILD, avalia eventos e persiste estado e histórico.

## Event engine

O motor recebe fatos/snapshot, avalia condições compostas e produz consequências declarativas. Persistência e publicação são coordenadas pelo serviço, permitindo auditoria, idempotência e eventos únicos/World First.

## Observabilidade

Cada tick deve carregar `world_id`, `tick_number`, duração, seed/identificador de RNG e contagens relevantes. Logs não substituem `SpeciesHistory` nem o histórico persistente de eventos.
