# Zevo MVP

Jogo persistente de evolução de espécies. O jogador `Zero` controla uma espécie por vez em `Eos-1`; espécies abandonadas tornam-se `WILD` e continuam na simulação.

## Executar

```bash
cp .env.example .env
docker compose up --build
```

Frontend: <http://localhost:5173>  
API/OpenAPI: <http://localhost:8000/docs>  
Health: <http://localhost:8000/health>

O PostgreSQL usa o volume `postgres_data`. Reiniciar containers preserva o estado.

## Desenvolvimento

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
npm --prefix frontend run build
docker compose config
```

Variáveis principais estão em `.env.example`: `DEV_MODE`, intervalo/gerações do tick e seed da simulação. Em DEV, use a interface ou `POST /api/dev/simulate` para avançar ticks e facilitar `GRAY_BLOOD`.

## Banco

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
docker compose down -v  # reset local destrutivo
```

Contratos concisos permanecem em `docs/`.

O loop de progresso usa recursos fisiológicos e respostas adaptativas declarativas em `game_data/evolutions/`; durante o processo, pressões ambientais enviesam mutação/seleção sem garantir upgrades.
