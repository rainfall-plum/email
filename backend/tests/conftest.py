import sys
import os
from pathlib import Path

import pytest

# TestClient lifespan must never submit real mail or launch a production queue worker.
os.environ["EMAIL_OUTBOUND_WORKER_ENABLED"] = "false"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def temporary_database(tmp_path, monkeypatch):
    database_path = tmp_path / "database.sqlite"
    monkeypatch.setenv("EMAIL_DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    return database_path


@pytest.fixture
def clean_app_modules(monkeypatch):
    """Keep settings and the SQLAlchemy engine isolated between auth tests."""
    import app.config.settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("EMAIL_BOOTSTRAP_ADMIN_USERNAME", "")
    monkeypatch.setenv("EMAIL_BOOTSTRAP_ADMIN_PASSWORD", "")
    yield
    settings_module.get_settings.cache_clear()
