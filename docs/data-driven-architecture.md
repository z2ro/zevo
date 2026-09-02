# Data-driven content

Engine = capabilities: algoritmos, SQL, RNG, transações e handlers registrados.
Content = composição: `game_data/` contém IDs, thresholds, modifiers e efeitos.
`backend/app/engine/content.py` valida YAML uma vez no import/startup; o tick usa
apenas os registries em memória.

Thresholds, chance base e multiplicador de DEV de eventos pertencem ao `game_data`.

Para adicionar conteúdo, crie um YAML em `game_data/events`, `actions` ou
`strategies` usando os campos validados por `ContentDefinition`. Conditions
usam `field` + `op` (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`) e podem ser
compostas com `all`, `any` e `not`. Effects só aceitam tipos registrados.

Para adicionar um evento com primitives existentes, crie principalmente um YAML;
uma nova capability exige handler Python e registro explícito. Validação:
`PYTHONPATH=backend python3 -c 'from app.engine import CONTENT'`.
Conteúdo inválido ou IDs duplicados interrompem o carregamento; não há `eval`,
`exec`, hot reload ou execução de código vindo dos arquivos.
