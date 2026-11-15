"""
API tests run against a real PostgreSQL database named by TEST_DATABASE_URL (no default, so no password
lives in the repo). The app seeds it from the committed NASA PSI snapshot on startup. The tests only
read data and clear the response cache, so pointing them at a development database is safe
(start.ps1 -Test does this for this process only).
WARNING: the Node suites (npm test) DROP the whole schema of their TEST_DATABASE_URL. Never leave
TEST_DATABASE_URL set to a database you care about in a shell where you also run npm test.
Without TEST_DATABASE_URL, or when the database is unreachable, the API tests are skipped with a reason.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":  # psycopg's async mode cannot use Windows' default ProactorEventLoop
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["FIF_ADMIN_TOKEN"] = "test-admin-token-0123456789"
os.environ["FIF_RATE_LIMIT_PER_MIN"] = "100000"
os.environ["FIF_AUTH_RATE_LIMIT_PER_MIN"] = "100000"
os.environ["SMTP_HOST"] = ""          # never send real email from tests; links go to the in-memory outbox
os.environ["FIF_PUBLIC_URL"] = ""
os.environ["FLAMEATLAS_URL"] = ""     # tests use a fake FlameAtlas (tests/test_atlas.py), never the real service


def _db_problem() -> str:
    """Why the API tests cannot run, or "" when the test database is reachable."""
    if not TEST_DB:
        return "TEST_DATABASE_URL is not set (run start.ps1 -Test, or set it to postgres://fif:PASSWORD@localhost:5432/fif_py_test)"
    try:
        import psycopg
        with psycopg.connect(TEST_DB, connect_timeout=5):
            return ""
    except Exception as e:  # wrong password, no server, missing database
        return f"cannot connect to TEST_DATABASE_URL: {str(e).strip().splitlines()[-1]}"


@pytest.fixture(scope="session")
def client():
    problem = _db_problem()
    if problem:
        pytest.skip(problem)
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    app = create_app(Settings())
    with TestClient(app) as c:
        yield c


ADMIN = {"Authorization": "Bearer test-admin-token-0123456789"}
