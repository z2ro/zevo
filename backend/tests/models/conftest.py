import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.db.base import Base
from app.db.session import create_engine_for_url


@pytest.fixture
def engine():
    value = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(value)
    yield value
    value.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as value:
        yield value
