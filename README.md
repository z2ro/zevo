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

Variáveis principais estão em `.env.example`: `DEV_MODE`, intervalo da simulação, escala planetária e seed. O scheduler executa aproximadamente a cada 5 segundos; a idade de Eos-1 deriva do tempo real (por padrão, 5 segundos ≈ 1.000 anos), enquanto gerações são individuais por linhagem. Em DEV, `POST /api/dev/simulate` recebe `{"steps": N}` e `/api/dev/reset-world` restaura o mundo ao ano 0.

## Banco

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
docker compose down -v  # reset local destrutivo
```

Contratos concisos permanecem em `docs/`.

O loop de progresso usa recursos fisiológicos e respostas adaptativas declarativas em `game_data/evolutions/`; durante o processo, pressões ambientais enviesam mutação/seleção sem garantir upgrades.
