import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DB_PATH = PROJECT_ROOT / "data" / "test_juriscan.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["APP_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _temp_data_dir(tmp_path_factory):
    """Redirect uploads to a temporary directory so tests never write into the
    real development ``data/uploads`` folder. Removed afterwards."""

    from app.config import settings

    original = settings.data_dir
    temp_root = tmp_path_factory.mktemp("juriscan-data")
    settings.data_dir = temp_root
    try:
        yield temp_root
    finally:
        settings.data_dir = original
        shutil.rmtree(temp_root, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    from main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_test_database():
    from app.core.database import Base, engine
    from app.core.logging import logger

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.debug("Test database reset")
    yield
    Base.metadata.drop_all(bind=engine)