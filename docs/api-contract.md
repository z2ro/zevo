# Contrato oficial da API — MVP v1

Base `/api`; JSON `snake_case`; UTC; IDs inteiros opacos. Erros: `{"error":{"code":"...","message":"...","details":{}}}`. Use 400 semântica, 404 ausente, 409 invariante, 422 formato. Player corrente é Zero sem autenticação.

Representações canônicas: `Species` expõe todos os campos e oito traits de `domain-model.md`; `World` expõe Eos-1, generation, tick, parâmetros, contagens, `dev_mode`; listas usam `{"items":[]}`. Histórico expõe `kind`, generation, title, description, species/player e metadata.

## Leituras

- `GET /health` → 200 `{"status":"ok","database":"ok"}`; `GET /metrics` → texto Prometheus.
- `GET /api/world`, `/api/world/species`, `/api/world/history?limit=100`, `/api/habitats`.
- `GET /api/species`, `/api/species/current` (404 se nenhuma), `/api/species/{id}`.
- `GET /api/events?limit=100`, `/api/legacy`, `/api/players/current`.

## Espécies e ações

`POST /api/species/preview` e `POST /api/species` recebem `name`, `species_type`, `energy_source`, `strategy`, `habitat_id`, `traits` (objeto com oito inteiros). Preview 200: `estimated_fitness`, `estimated_growth` (`positive|stable|negative`), `risk`, `environment_compatibility`. Criação 201 retorna Species; 409 se já controla uma.

- `POST /api/species/{id}/migrate`: `{"destination_habitat_id":2,"population_fraction":0.5}` → 202 PlayerAction.
- `POST /api/species/{id}/split`: `{"population_fraction":0.25}` → 200 Species com founder effect.
- `POST /api/species/{id}/strategy`: `{"strategy":"RESISTANT"}` → 200 Species.
- `POST /api/species/{id}/focus-reproduction` e `/focus-survival`: `{}` → 202 PlayerAction.
- `POST /api/species/{id}/abandon`: `{}` → 200 Species WILD.

Somente espécie corrente aceita comandos; caso contrário 409. Frações são `(0,1]` para migration e `(0,1)` para split.

## DEV

`POST /api/dev/simulate` recebe `{"ticks":1..1000,"evaluate_events":true}` e retorna World. Apenas `DEV_MODE=true`; fora dele retorna 404. Chamadas são serializadas com o scheduler.

Campos incompatíveis exigem atualização deste documento e handoff; o frontend não replica cálculo canônico.
