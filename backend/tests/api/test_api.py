import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.bootstrap import bootstrap_world
from app.main import app, db_dependency
from app.config.settings import get_settings
from app.models.entities import GameEvent, Player, World
from app.models.enums import EventRarity


@pytest.fixture
def anyio_backend(): return "asyncio"


@pytest.mark.anyio
async def test_health_world_and_species_flow(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine); bootstrap_world(session); session.close()
    factory = sessionmaker(engine, expire_on_commit=False)
    async def override():
        with factory() as value: yield value
    app.dependency_overrides[db_dependency] = override
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/api/world")).json()["name"] == "Eos-1"
    assert (await client.get("/api/players/current")).json()["current_species_id"] is None
    habitat_items = (await client.get("/api/habitats")).json()["items"]
    habitat = habitat_items[0]["id"]
    payload = {"name": "Prima", "species_type": "AUTOTROPH", "energy_source": "SOLAR",
        "strategy": "COLONIZER", "habitat_id": habitat, "traits": {
            "thermal_tolerance": 12, "radiation_tolerance": 12, "ph_tolerance": 12,
            "metabolic_efficiency": 12, "reproduction_rate": 12, "mutation_rate": 12,
            "energy_efficiency": 12, "structural_resistance": 12}}
    assert (await client.post("/api/species/preview", json=payload)).status_code == 200
    created = await client.post("/api/species", json=payload)
    assert created.status_code == 201
    created_json = created.json()
    assert created_json["traits"]["thermal_tolerance"] == 12
    assert "thermal_tolerance" not in created_json
    current = (await client.get("/api/species/current")).json()
    assert current["traits"] == created_json["traits"]
    responses = (await client.get(f"/api/species/{created_json['id']}/evolutions")).json()["items"]
    metabolic = next(item for item in responses if item["id"] == "METABOLIC_EFFICIENCY_I")
    assert metabolic["available"] is True and metabolic["can_start"] is True and metabolic["blocked_reason"] is None
    assert (await client.post(f"/api/species/{created_json['id']}/evolutions/{metabolic['id']}")).status_code == 202
    active_responses = (await client.get(f"/api/species/{created_json['id']}/evolutions")).json()["items"]
    assert all(item["can_start"] is False and item["blocked_reason"] == "RESPONSE_ACTIVE" for item in active_responses)
    assert "traits" in (await client.get(f"/api/species/{created_json['id']}")).json()
    assert "traits" in (await client.get("/api/species")).json()["items"][0]
    assert "traits" in (await client.post(f"/api/species/{created_json['id']}/split", json={})).json()
    assert "traits" in (await client.post(f"/api/species/{created_json['id']}/strategy", json={"strategy": "COMPETITOR"})).json()
    focus = (await client.post(f"/api/species/{created_json['id']}/focus-reproduction")).json()
    assert "payload" in focus and "metadata" not in focus
    migration = (await client.post(f"/api/species/{created_json['id']}/migrate", json={
        "destination_habitat_id": habitat_items[1]["id"]})).json()
    assert "payload" in migration
    duplicate = await client.post("/api/species", json=payload)
    assert duplicate.status_code == 409 and set(duplicate.json()) == {"error"}
    assert duplicate.json()["error"]["code"] == "controlled_species_exists"
    invalid = await client.post("/api/species", json={"name": "incomplete"})
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "validation_error"
    assert (await client.get("/api/players/current")).json()["current_species_id"] == created_json["id"]
    legacy = (await client.get("/api/legacy")).json()
    assert {"active", "wild", "extinct", "total_population", "world_firsts"} <= legacy.keys()
    assert legacy["active"] == 1 and legacy["wild"] == 0

    with factory() as event_session:
        player = event_session.scalar(select(Player).where(Player.username == "Zero"))
        eos = event_session.scalar(select(World).where(World.name == "Eos-1"))
        event_session.add(GameEvent(world_id=eos.id, code="TEST_FIRST", name="Test First",
            description="Contract event", rarity=EventRarity.WORLD_FIRST, planet_age_years=eos.age_years,
            historical=True, global_unique=True, repeat_scope="WORLD", player_id=player.id,
            species_id=created_json["id"], event_metadata={"source": "test"}))
        event_session.commit()
    event = (await client.get("/api/events")).json()["items"][0]
    assert event["metadata"] == {"source": "test"} and "event_metadata" not in event
    assert (await client.get("/api/world/history")).json()["items"][0]["metadata"] == {"source": "test"}
    assert (await client.get("/api/legacy")).json()["world_firsts"][0]["metadata"] == {"source": "test"}

    abandoned = (await client.post(f"/api/species/{created_json['id']}/abandon")).json()
    assert abandoned["status"] == "WILD" and "traits" in abandoned
    payload["name"] = "Secunda"
    second = await client.post("/api/species", json=payload)
    assert second.status_code == 201
    all_species = (await client.get("/api/world/species")).json()["items"]
    assert any(s["id"] == created_json["id"] and s["status"] == "WILD" and "traits" in s for s in all_species)
    assert (await client.post("/api/dev/simulate", json={"steps": 1})).status_code == 404
    monkeypatch.setenv("DEV_MODE", "true"); get_settings.cache_clear()
    simulated = (await client.post("/api/dev/simulate", json={"steps": 1})).json()
    assert simulated["simulation_step"] == 1 and simulated["age_years"] >= 1_000
    reset = (await client.post("/api/dev/reset-world", json={})).json()
    assert reset == {"age_years": 0, "simulation_step": 0}
    assert (await client.get("/api/species/current")).status_code == 404
    assert (await client.get("/api/events")).json()["items"] == []
    assert (await client.get("/api/players/current")).json()["id"] == player.id
    get_settings.cache_clear()
    await client.aclose(); app.dependency_overrides.clear(); engine.dispose()
