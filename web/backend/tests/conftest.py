import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

TEST_DATABASE_DIR = Path(tempfile.mkdtemp(prefix="project5-tests-"))
TEST_ARTIFACT_DIR = Path(tempfile.mkdtemp(prefix="project5-benchmark-artifacts-"))
TEST_DATABASE_URL = os.environ.get(
    "PROJECT5_TEST_DATABASE_URL",
    f"sqlite+aiosqlite:///{(TEST_DATABASE_DIR / 'content_governance.db').as_posix()}",
)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BENCHMARK_ARTIFACT_ROOT"] = os.environ.get(
    "PROJECT5_TEST_BENCHMARK_ARTIFACT_ROOT",
    str(TEST_ARTIFACT_DIR),
)
# Avoid importing the full in-repo value_qa pack on every TestClient lifespan.
os.environ.setdefault("TOPIC1_VALUE_QA_AUTO_ENSURE", "false")
# Governance assistant tests use the deterministic stub, never a live model host.
os.environ["GOVERNANCE_ASSISTANT_PROVIDER"] = "stub"
# Legacy governance capability tests exercise the Phase 1 interpreter path.
# Skill Runtime coverage opts into "on" explicitly in its dedicated tests.
os.environ["GOVERNANCE_SKILL_RUNTIME_MODE"] = "off"

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


def _assert_test_database() -> None:
    database_url = str(engine.url)
    if not _is_safe_test_database_url(database_url):
        raise RuntimeError(
            f"Refusing to reset non-test database during pytest: {database_url}"
        )


def _is_safe_test_database_url(database_url: str) -> bool:
    if not database_url.startswith("sqlite"):
        return False
    if "project5-tests-" in database_url:
        return True

    parsed = urlparse(database_url)
    raw_path = unquote(parsed.path or "")
    if not raw_path:
        return False

    path = Path(raw_path)
    return path.name.startswith("test_")


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    _assert_test_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
def default_topic1_local_adapter(monkeypatch):
    monkeypatch.setenv("TOPIC1_ALGORITHM_MODE", "local_adapter")


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sync_client():
    with TestClient(app) as client:
        yield client
