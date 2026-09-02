from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.bootstrap import bootstrap_world
from app.db.session import create_engine_for_url
from app.models import Habitat, Player, World


def test_concurrent_bootstrap_is_safe(tmp_path):
    engine = create_engine_for_url(f"sqlite+pysqlite:///{tmp_path / 'bootstrap.db'}")
    Base.metadata.create_all(engine)

    def run():
        with Session(engine) as session:
            return bootstrap_world(session).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: run(), range(2)))
    with Session(engine) as session:
        assert ids[0] == ids[1]
        assert len(session.scalars(select(World)).all()) == 1
        assert len(session.scalars(select(Habitat)).all()) == 5
        assert len(session.scalars(select(Player)).all()) == 6
    engine.dispose()
