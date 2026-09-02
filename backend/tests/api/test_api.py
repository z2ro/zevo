import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.bootstrap import bootstrap_world
from app.main import app, db_dependency
from app.config.settings import get_settings


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
    habitat = (await client.get("/api/habitats")).json()["items"][0]["id"]
    payload = {"name": "Prima", "species_type": "AUTOTROPH", "energy_source": "SOLAR",
        "strategy": "COLONIZER", "habitat_id": habitat, "traits": {
            "thermal_tolerance": 12, "radiation_tolerance": 12, "ph_tolerance": 12,
            "metabolic_efficiency": 12, "reproduction_rate": 12, "mutation_rate": 12,
            "energy_efficiency": 12, "structural_resistance": 12}}
    assert (await client.post("/api/species/preview", json=payload)).status_code == 200
    created = await client.post("/api/species", json=payload)
    assert created.status_code == 201
    assert (await client.post(f"/api/species/{created.json()['id']}/abandon")).json()["status"] == "WILD"
    assert (await client.post("/api/dev/simulate", json={"ticks": 1})).status_code == 404
    monkeypatch.setenv("DEV_MODE", "true"); get_settings.cache_clear()
    assert (await client.post("/api/dev/simulate", json={"ticks": 1})).json()["tick"] == 1
    get_settings.cache_clear()
    await client.aclose(); app.dependency_overrides.clear(); engine.dispose()
