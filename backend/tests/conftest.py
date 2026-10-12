import sys
import os
import tempfile
from pathlib import Path

import pytest

# TestClient lifespan must never submit real mail or launch a production queue worker.
os.environ["EMAIL_OUTBOUND_WORKER_ENABLED"] = "false"
# Establish safe defaults before importing app.main or its module-level engine.
# Individual tests can still override these paths with their own tmp_path.
_suite_directory = tempfile.TemporaryDirectory(prefix="email-platform-pytest-")
_suite_root = Path(_suite_directory.name)
os.environ["EMAIL_DATABASE_URL"] = f"sqlite:///{(_suite_root / 'suite.sqlite').as_posix()}"
os.environ["EMAIL_DATA_DIR"] = str(_suite_root)
os.environ["EMAIL_LOG_DIR"] = str(_suite_root / "logs")
os.environ["EMAIL_NAMES_DIR"] = str(_suite_root / "names")
os.environ["EMAIL_BOOTSTRAP_ADMIN_USERNAME"] = ""
os.environ["EMAIL_BOOTSTRAP_ADMIN_PASSWORD"] = ""


def pytest_unconfigure(config):
    import logging
    logging.shutdown()
    module = sys.modules.get("app.database.session")
    if module:
        module.engine.dispose()
    _suite_directory.cleanup()

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
