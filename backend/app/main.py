from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.bootstrap import bootstrap_world
from app.db.session import get_session_factory
from app.models.entities import GameEvent, Habitat, Player, PlayerAction, Species, SpeciesPopulationSnapshot, SpeciesTraitHistory, World, WorldSnapshot
from app.models.enums import ActionType, SpeciesStatus, Strategy
from app.schemas.species import SpeciesCreate, SpeciesRead
from app.services.action_service import ActionServiceError, change_strategy, queue_focus, queue_migration, split_species
from app.services.scheduler import start_scheduler
from app.services.simulation_service import SimulationService
from app.services.species_service import SpeciesServiceError, abandon_species, create_species, preview_species


@asynccontextmanager
async def lifespan(_: FastAPI):
    with get_session_factory()() as session:
        bootstrap_world(session)
    stop, thread = start_scheduler()
    yield
    stop.set(); thread.join(timeout=1)


app = FastAPI(title="Zevo", version="0.1.0", lifespan=lifespan)


async def db_dependency():
    with get_session_factory()() as session:
        yield session


Db = Annotated[Session, Depends(db_dependency)]


class MigrationBody(BaseModel):
    destination_habitat_id: int
    population_fraction: float = Field(gt=0, le=1)


class SplitBody(BaseModel): population_fraction: float = Field(gt=0, lt=1)
class StrategyBody(BaseModel): strategy: Strategy
class SimulateBody(BaseModel): ticks: int = Field(ge=1, le=1000); evaluate_events: bool = True


def row(value):
    return jsonable_encoder({column.key: getattr(value, column.key) for column in value.__mapper__.columns})


def zero(session: Session) -> Player:
    player = session.scalar(select(Player).where(Player.username == "Zero"))
    if not player: raise HTTPException(404, "Player Zero not initialized")
    return player


def world(session: Session) -> World:
    value = session.scalar(select(World).where(World.name == "Eos-1"))
    if not value: raise HTTPException(404, "World not initialized")
    return value


def service_error(exc: Exception):
    if isinstance(exc, (SpeciesServiceError, ActionServiceError)):
        raise HTTPException(exc.status_code, exc.as_error() if isinstance(exc, SpeciesServiceError) else {"error": {"code": exc.code, "message": exc.message, "details": {}}})
    raise exc


@app.get("/health")
async def health(db: Db):
    db.execute(text("SELECT 1")); return {"status": "ok", "database": "ok"}


@app.get("/metrics")
async def metrics(db: Db):
    alive = db.scalar(select(func.count()).select_from(Species).where(Species.status != SpeciesStatus.EXTINCT)) or 0
    extinct = db.scalar(select(func.count()).select_from(Species).where(Species.status == SpeciesStatus.EXTINCT)) or 0
    events = db.scalar(select(func.count()).select_from(GameEvent)) or 0
    ticks = db.scalar(select(func.coalesce(func.sum(World.tick), 0))) or 0
    body = f"simulation_ticks_total {ticks}\nspecies_alive {alive}\nspecies_extinct_total {extinct}\nevents_total {events}\n"
    return Response(body, media_type="text/plain; version=0.0.4")


@app.get("/api/world")
async def get_world(db: Db):
    value = world(db); data = row(value)
    data.update(dev_mode=get_settings().dev_mode,
        species_alive=db.scalar(select(func.count()).select_from(Species).join(Habitat).where(Habitat.world_id == value.id, Species.status != SpeciesStatus.EXTINCT)),
        species_extinct=db.scalar(select(func.count()).select_from(Species).join(Habitat).where(Habitat.world_id == value.id, Species.status == SpeciesStatus.EXTINCT)))
    return data


@app.get("/api/world/species")
async def world_species(db: Db): return {"items": [row(x) for x in db.scalars(select(Species).join(Habitat).where(Habitat.world_id == world(db).id).order_by(Species.id))]}


@app.get("/api/habitats")
async def habitats(db: Db): return {"items": [row(x) for x in db.scalars(select(Habitat).where(Habitat.world_id == world(db).id).order_by(Habitat.id))]}


@app.get("/api/species")
async def species(db: Db): return {"items": [row(x) for x in db.scalars(select(Species).order_by(Species.id))]}


@app.get("/api/species/current")
async def current_species(db: Db):
    value = db.scalar(select(Species).where(Species.creator_id == zero(db).id, Species.is_player_controlled.is_(True)))
    if not value: raise HTTPException(404, "No controlled species")
    return row(value)


@app.get("/api/species/{species_id}")
async def species_detail(species_id: int, db: Db):
    value = db.get(Species, species_id)
    if not value: raise HTTPException(404, "Species not found")
    data = row(value)
    data["population_history"] = [row(x) for x in db.scalars(select(SpeciesPopulationSnapshot).where(SpeciesPopulationSnapshot.species_id == species_id).order_by(SpeciesPopulationSnapshot.id.desc()).limit(100))]
    data["trait_history"] = [row(x) for x in db.scalars(select(SpeciesTraitHistory).where(SpeciesTraitHistory.species_id == species_id).order_by(SpeciesTraitHistory.id.desc()).limit(100))]
    return data


@app.post("/api/species/preview")
async def preview(data: SpeciesCreate, db: Db): return preview_species(db, data)


@app.post("/api/species", status_code=201)
async def create(data: SpeciesCreate, db: Db):
    try: value = create_species(db, zero(db).id, data); db.commit(); return row(value)
    except (SpeciesServiceError, ActionServiceError) as exc: service_error(exc)


def action(call, db: Session):
    try: value = call(); db.commit(); return row(value)
    except (SpeciesServiceError, ActionServiceError) as exc: service_error(exc)


@app.post("/api/species/{species_id}/migrate", status_code=202)
async def migrate(species_id: int, body: MigrationBody, db: Db): return action(lambda: queue_migration(db, zero(db).id, species_id, body.destination_habitat_id, body.population_fraction), db)


@app.post("/api/species/{species_id}/split")
async def split(species_id: int, body: SplitBody, db: Db): return action(lambda: split_species(db, zero(db).id, species_id, body.population_fraction), db)


@app.post("/api/species/{species_id}/strategy")
async def strategy(species_id: int, body: StrategyBody, db: Db): return action(lambda: change_strategy(db, zero(db).id, species_id, body.strategy), db)


@app.post("/api/species/{species_id}/focus-reproduction", status_code=202)
async def focus_reproduction(species_id: int, db: Db): return action(lambda: queue_focus(db, zero(db).id, species_id, ActionType.FOCUS_REPRODUCTION), db)


@app.post("/api/species/{species_id}/focus-survival", status_code=202)
async def focus_survival(species_id: int, db: Db): return action(lambda: queue_focus(db, zero(db).id, species_id, ActionType.FOCUS_SURVIVAL), db)


@app.post("/api/species/{species_id}/abandon")
async def abandon(species_id: int, db: Db): return action(lambda: abandon_species(db, zero(db).id, species_id), db)


@app.get("/api/events")
async def events(db: Db, limit: int = Query(100, ge=1, le=1000)): return {"items": [row(x) for x in db.scalars(select(GameEvent).order_by(GameEvent.generation.desc()).limit(limit))]}


@app.get("/api/world/history")
async def history(db: Db, limit: int = Query(100, ge=1, le=1000)):
    items = [{"kind": "event", "generation": e.generation, "title": e.name, "description": e.description, "species_id": e.species_id, "player_id": e.player_id, "metadata": e.event_metadata} for e in db.scalars(select(GameEvent).order_by(GameEvent.generation.desc()).limit(limit))]
    return {"items": items[:limit]}


@app.get("/api/legacy")
async def legacy(db: Db):
    player = zero(db); items = list(db.scalars(select(Species).where(Species.creator_id == player.id).order_by(Species.id)))
    return {"player": row(player), "total_species": len(items), "alive": sum(s.status != SpeciesStatus.EXTINCT for s in items), "wild": sum(s.status == SpeciesStatus.WILD for s in items), "extinct": sum(s.status == SpeciesStatus.EXTINCT for s in items), "current_population": sum(s.population for s in items), "species": [row(s) for s in items]}


@app.get("/api/players/current")
async def current_player(db: Db): return row(zero(db))


@app.post("/api/dev/simulate")
async def simulate(body: SimulateBody, db: Db):
    if not get_settings().dev_mode: raise HTTPException(404, "DEV mode disabled")
    value = world(db); service = SimulationService()
    for _ in range(body.ticks): service.run_tick(db, value.id)
    db.commit(); db.refresh(value); return row(value)
