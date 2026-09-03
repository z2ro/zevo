from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.config.game_balance import BALANCE
from app.engine import CONTENT
from app.db.bootstrap import bootstrap_world
from app.db.session import get_session_factory
from app.models.entities import GameEvent, Habitat, Player, PlayerAction, Species, SpeciesEvolution, SpeciesPopulationSnapshot, SpeciesTraitHistory, World, WorldSnapshot
from app.models.enums import ActionType, EventRarity, SpeciesStatus, Strategy
from app.schemas.species import SpeciesCreate, SpeciesRead
from app.services.action_service import ActionServiceError, change_strategy, queue_focus, queue_migration, split_species
from app.services.scheduler import start_scheduler
from app.services.simulation_service import SimulationService
from app.services.species_service import SpeciesServiceError, abandon_species, create_species, preview_species
from app.services.evolution_service import EvolutionServiceError, adaptive_response_eligibility, pressures_for_species, start_evolution


@asynccontextmanager
async def lifespan(_: FastAPI):
    with get_session_factory()() as session:
        bootstrap_world(session)
    stop, thread = start_scheduler()
    yield
    stop.set(); thread.join(timeout=1)


app = FastAPI(title="Zevo", version="0.1.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) and "error" in exc.detail else {
        "error": {"code": "not_found" if exc.status_code == 404 else "http_error",
                   "message": str(exc.detail), "details": {}}
    }
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {
        "code": "validation_error", "message": "Invalid request", "details": {"errors": jsonable_encoder(exc.errors())}
    }})


async def db_dependency():
    with get_session_factory()() as session:
        yield session


Db = Annotated[Session, Depends(db_dependency)]


class MigrationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_habitat_id: int


class SplitBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
class StrategyBody(BaseModel): strategy: Strategy
class SimulateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticks: int = Field(ge=1, le=1000)


TRAIT_FIELDS = (
    "thermal_tolerance", "radiation_tolerance", "ph_tolerance",
    "metabolic_efficiency", "reproduction_rate", "mutation_rate",
    "energy_efficiency", "structural_resistance",
)


def row(value):
    return jsonable_encoder({field.key: getattr(value, field.key) for field in value.__mapper__.column_attrs})


def serialize_species(value: Species):
    data = row(value)
    data["traits"] = {name: data.pop(name) for name in TRAIT_FIELDS}
    rate = max(0, round(value.population * max(0.0, value.fitness)))
    biomass_rate = max(1, round(rate * BALANCE.resource_biomass_rate))
    energy_rate = max(1, round(rate * BALANCE.resource_energy_rate))
    genetic_rate = max(1, round(rate * BALANCE.resource_genetic_rate))
    data["resources"] = {"biomass": value.biomass, "energy": value.energy, "genetic_material": value.genetic_material, "adaptation_points": value.adaptation_points}
    data["resource_rates"] = {"biomass": biomass_rate, "energy": energy_rate, "genetic_material": genetic_rate}
    return data


def serialize_event(value: GameEvent):
    data = row(value)
    data["metadata"] = data.pop("event_metadata")
    return data


def serialize_player(value: Player, session: Session):
    data = row(value)
    data["current_species_id"] = session.scalar(select(Species.id).where(
        Species.creator_id == value.id, Species.is_player_controlled.is_(True)))
    return data


def serialize_action(value: PlayerAction):
    return row(value)


def serialize_result(value):
    if isinstance(value, Species): return serialize_species(value)
    if isinstance(value, GameEvent): return serialize_event(value)
    if isinstance(value, PlayerAction): return serialize_action(value)
    return row(value)


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
async def world_species(db: Db): return {"items": [serialize_species(x) for x in db.scalars(select(Species).join(Habitat).where(Habitat.world_id == world(db).id).order_by(Species.id))]}


@app.get("/api/habitats")
async def habitats(db: Db): return {"items": [row(x) for x in db.scalars(select(Habitat).where(Habitat.world_id == world(db).id).order_by(Habitat.id))]}


@app.get("/api/species")
async def species(db: Db): return {"items": [serialize_species(x) for x in db.scalars(select(Species).order_by(Species.id))]}


@app.get("/api/species/current")
async def current_species(db: Db):
    value = db.scalar(select(Species).where(Species.creator_id == zero(db).id, Species.is_player_controlled.is_(True)))
    if not value: raise HTTPException(404, "No controlled species")
    return serialize_species(value)


@app.get("/api/species/{species_id}")
async def species_detail(species_id: int, db: Db):
    value = db.get(Species, species_id)
    if not value: raise HTTPException(404, "Species not found")
    data = serialize_species(value)
    data["population_history"] = [row(x) for x in db.scalars(select(SpeciesPopulationSnapshot).where(SpeciesPopulationSnapshot.species_id == species_id).order_by(SpeciesPopulationSnapshot.id.desc()).limit(100))]
    data["trait_history"] = [row(x) for x in db.scalars(select(SpeciesTraitHistory).where(SpeciesTraitHistory.species_id == species_id).order_by(SpeciesTraitHistory.id.desc()).limit(100))]
    return data


@app.get("/api/species/{species_id}/evolutions")
async def species_evolutions(species_id: int, db: Db):
    if not db.get(Species, species_id): raise HTTPException(404, "Species not found")
    species = db.get(Species, species_id)
    current_tick = db.scalar(select(World.tick).join(Habitat, Habitat.world_id == World.id).where(Habitat.id == species.habitat_id)) or 0
    items = []
    for key, spec in sorted(CONTENT["evolutions"].items()):
        available, can_start, blocked_reason = adaptive_response_eligibility(db, species, spec)
        process = db.scalar(select(SpeciesEvolution).where(SpeciesEvolution.species_id == species_id, SpeciesEvolution.evolution_id == key).order_by(SpeciesEvolution.id.desc()))
        items.append({"id": key, "name": spec.name, "category": spec.category, "level": spec.level, "cost": spec.cost, "duration_ticks": spec.duration_ticks, "requirements": spec.requirements, "pressure": spec.pressure, "selection_bias": spec.selection_bias, "tradeoffs": spec.tradeoffs, "available": available, "can_start": can_start, "blocked_reason": blocked_reason, "status": process.status if process else None, "ticks_remaining": max(0, process.complete_at_tick - current_tick) if process and process.status.value == "IN_PROGRESS" else None})
    return {"items": items}


@app.get("/api/species/{species_id}/pressures")
async def species_pressures(species_id: int, db: Db):
    species = db.get(Species, species_id)
    if not species: raise HTTPException(404, "Species not found")
    return {"items": [p.__dict__ for p in pressures_for_species(db, species)]}


@app.post("/api/species/{species_id}/evolutions/{evolution_id}", status_code=202)
async def begin_evolution(species_id: int, evolution_id: str, db: Db):
    try:
        result = start_evolution(db, zero(db).id, species_id, evolution_id, world(db).tick); db.commit(); return row(result)
    except EvolutionServiceError as exc:
        raise HTTPException(exc.status_code, {"error": {"code": exc.code, "message": exc.message, "details": {}}})


@app.post("/api/species/preview")
async def preview(data: SpeciesCreate, db: Db): return preview_species(db, data)


@app.post("/api/species", status_code=201)
async def create(data: SpeciesCreate, db: Db):
    try: value = create_species(db, zero(db).id, data); db.commit(); return serialize_species(value)
    except (SpeciesServiceError, ActionServiceError) as exc: service_error(exc)


def action(call, db: Session):
    try: value = call(); db.commit(); return serialize_result(value)
    except (SpeciesServiceError, ActionServiceError) as exc: service_error(exc)


@app.post("/api/species/{species_id}/migrate", status_code=202)
async def migrate(species_id: int, body: MigrationBody, db: Db): return action(lambda: queue_migration(db, zero(db).id, species_id, body.destination_habitat_id), db)


@app.post("/api/species/{species_id}/split")
async def split(species_id: int, body: SplitBody, db: Db): return action(lambda: split_species(db, zero(db).id, species_id, BALANCE.founder_expedition_fraction), db)


@app.post("/api/species/{species_id}/strategy")
async def strategy(species_id: int, body: StrategyBody, db: Db): return action(lambda: change_strategy(db, zero(db).id, species_id, body.strategy), db)


@app.post("/api/species/{species_id}/focus-reproduction", status_code=202)
async def focus_reproduction(species_id: int, db: Db): return action(lambda: queue_focus(db, zero(db).id, species_id, ActionType.FOCUS_REPRODUCTION), db)


@app.post("/api/species/{species_id}/focus-survival", status_code=202)
async def focus_survival(species_id: int, db: Db): return action(lambda: queue_focus(db, zero(db).id, species_id, ActionType.FOCUS_SURVIVAL), db)


@app.post("/api/species/{species_id}/abandon")
async def abandon(species_id: int, db: Db): return action(lambda: abandon_species(db, zero(db).id, species_id), db)


@app.get("/api/events")
async def events(db: Db, limit: int = Query(100, ge=1, le=1000)): return {"items": [serialize_event(x) for x in db.scalars(select(GameEvent).order_by(GameEvent.generation.desc()).limit(limit))]}


@app.get("/api/world/history")
async def history(db: Db, limit: int = Query(100, ge=1, le=1000)):
    items = [{"kind": "event", "generation": event["generation"], "title": event["name"], "description": event["description"], "species_id": event["species_id"], "player_id": event["player_id"], "metadata": event["metadata"]} for event in (serialize_event(e) for e in db.scalars(select(GameEvent).order_by(GameEvent.generation.desc()).limit(limit)))]
    return {"items": items[:limit]}


@app.get("/api/legacy")
async def legacy(db: Db):
    player = zero(db); items = list(db.scalars(select(Species).where(Species.creator_id == player.id).order_by(Species.id)))
    world_firsts = list(db.scalars(select(GameEvent).where(
        GameEvent.player_id == player.id, GameEvent.rarity == EventRarity.WORLD_FIRST
    ).order_by(GameEvent.generation.desc())))
    return {"total_species": len(items), "active": sum(s.status == SpeciesStatus.ACTIVE for s in items),
        "wild": sum(s.status == SpeciesStatus.WILD for s in items),
        "extinct": sum(s.status == SpeciesStatus.EXTINCT for s in items),
        "total_population": sum(s.population for s in items if s.status != SpeciesStatus.EXTINCT),
        "species": [serialize_species(s) for s in items],
        "world_firsts": [serialize_event(event) for event in world_firsts]}


@app.get("/api/players/current")
async def current_player(db: Db): return serialize_player(zero(db), db)


@app.post("/api/dev/simulate")
async def simulate(body: SimulateBody, db: Db):
    if not get_settings().dev_mode: raise HTTPException(404, "DEV mode disabled")
    value = world(db); service = SimulationService()
    for _ in range(body.ticks): service.run_tick(db, value.id)
    db.commit(); db.refresh(value); return row(value)
