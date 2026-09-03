# Contrato oficial da API — MVP v1

Base `/api`; JSON `snake_case`; UTC; IDs inteiros opacos. Erros: `{"error":{"code":"...","message":"...","details":{}}}`. Use 400 semântica, 404 ausente, 409 invariante, 422 formato. Player corrente é Zero sem autenticação.

Representações canônicas: `Species` agrupa os oito traits em `traits`; `GameEvent` expõe `planet_age_years` e a coluna interna `event_metadata` como `metadata`; `PlayerAction` usa `payload`; `Player` inclui `current_species_id`. `World` expõe `age_years`, parâmetros, contagens e `dev_mode`; o passo técnico não é cronologia pública. Listas usam `{"items":[]}`.

## Leituras

- `GET /health` → 200 `{"status":"ok","database":"ok"}`; `GET /metrics` → texto Prometheus.
- `GET /api/world`, `/api/world/species`, `/api/world/history?limit=100`, `/api/habitats`.
- `GET /api/species`, `/api/species/current` (404 se nenhuma), `/api/species/{id}`.
- `GET /api/events?limit=100`, `/api/legacy`, `/api/players/current`.

`GET /api/legacy` retorna `total_species`, `active`, `wild`, `extinct`, `total_population`, `species` e `world_firsts` do jogador Zero.

## Espécies e ações

`POST /api/species/preview` e `POST /api/species` recebem `name`, `species_type`, `energy_source`, `strategy`, `habitat_id`, `traits` (objeto com oito inteiros). Preview 200: `estimated_fitness`, `estimated_growth` (`positive|stable|negative`), `risk`, `environment_compatibility`. Criação 201 retorna Species; 409 se já controla uma.

- `POST /api/species/{id}/migrate`: `{"destination_habitat_id":2}` → 202 PlayerAction; migra toda a população com mortalidade de trânsito.
- `POST /api/species/{id}/split`: `{}` → 200 Species com Expedição Fundadora agregada; a fração é configurada pelo balanceamento (25% atualmente), sem subpopulação.
- `POST /api/species/{id}/strategy`: `{"strategy":"RESISTANT"}` → 200 Species.
- `POST /api/species/{id}/focus-reproduction` e `/focus-survival`: `{}` → 202 PlayerAction.
- `POST /api/species/{id}/abandon`: `{}` → 200 Species WILD.
- Species responses include `resources` (`biomass`, `energy`, `genetic_material`, `adaptation_points`) and rates per simulation update.
- `GET /api/species/{id}/evolutions` lists adaptive responses; `POST /api/species/{id}/evolutions/{evolution_id}` deducts its physiological cost and starts one timed response (202). While active it biases mutation/selection and applies declared population trade-offs; completion grants no trait directly.
- `GET /api/species/{id}/pressures` returns current ecological pressures (`type`, `score`, `severity`, `description`); responses with a declared pressure are available only when that pressure reaches its minimum severity.

Somente espécie corrente aceita comandos; caso contrário 409. A fração permanece apenas na Expedição Fundadora.

## DEV

`POST /api/dev/simulate` recebe `{"steps":1..1000}` e retorna `simulation_step` e `age_years`. `POST /api/dev/reset-world` apaga o estado de gameplay, preserva players e restaura Eos-1/habitats; os bots recriam linhagens pelo ciclo normal após o reset. Ambos existem apenas com `DEV_MODE=true` e são serializados pelo lock do mundo.

Campos incompatíveis exigem atualização deste documento; o frontend não replica cálculo canônico.
