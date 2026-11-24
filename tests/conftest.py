import pytest
from app.db import connect, init_db
from app.seed_dev import seed


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


@pytest.fixture
def period_id(conn):
    return seed(conn)
