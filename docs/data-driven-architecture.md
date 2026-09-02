# Data-driven content

`backend/app/engine/content.py` carrega e valida YAML uma vez no import/startup;
o tick usa apenas os registries em memória. A engine mantém algoritmos, SQL,
RNG e transações; `game_data/` contém IDs, thresholds, modifiers e efeitos.

Para adicionar conteúdo, crie um YAML em `game_data/events`, `actions` ou
`strategies` usando os campos validados por `ContentDefinition`. Conditions
usam `field` + `op` (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`) e podem ser
compostas com `all`, `any` e `not`. Effects só aceitam tipos registrados.

Validação: `PYTHONPATH=backend python3 -c 'from app.engine import CONTENT'`.
Conteúdo inválido ou IDs duplicados interrompem o carregamento; não há `eval`,
`exec`, hot reload ou execução de código vindo dos arquivos.
