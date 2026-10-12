"""Credential changes use disposable databases and randomly generated test secrets."""
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, get_settings
from app.models import AdminUser, Base
from app.routers.auth import get_db, router
from app.schemas.auth import CredentialsRequest
from app.services.admin_service import CredentialsError, change_credentials, ensure_bootstrap_admin
from app.utils.security import hash_password, verify_password


@pytest.fixture(scope="module")
def credential_secrets():
    current, replacement = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    return current, replacement, hash_password(current)


@pytest.fixture
def credential_env(tmp_path, monkeypatch, credential_secrets):
    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", secrets.token_urlsafe(48))
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'credentials.sqlite'}", connect_args={"check_same_thread": False}, hide_parameters=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(AdminUser(username="testadmin", password_hash=credential_secrets[2]))
        db.commit()
    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):
        return JSONResponse(status_code=422, content={"detail": "请求参数无效"})

    def database():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, factory, credential_secrets
    engine.dispose()
    get_settings.cache_clear()


def login(client, password, username="testadmin"):
    return client.post("/api/login", json={"username": username, "password": password})


def headers(client, password, username="testadmin"):
    result = login(client, password, username)
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def test_profile_and_missing_auth(credential_env):
    client, _, (current, _, _) = credential_env
    assert client.get("/api/admin/profile").status_code == 401
    response = client.get("/api/admin/profile", headers=headers(client, current))
    assert response.json() == {"id": 1, "username": "testadmin"}


@pytest.mark.parametrize("mode", ["username", "password", "both"])
def test_change_credentials_revokes_every_session(credential_env, mode):
    client, factory, (current, replacement, previous_hash) = credential_env
    session_a, session_b = headers(client, current), headers(client, current)
    assert session_a != session_b
    payload = {"current_password": current}
    new_username = "testadmin"
    new_password = current
    if mode in {"username", "both"}:
        payload["new_username"] = new_username = "renamed_admin"
    if mode in {"password", "both"}:
        payload["new_password"] = new_password = replacement
        payload["confirm_new_password"] = replacement
    result = client.patch("/api/admin/credentials", json=payload, headers=session_a)
    assert result.status_code == 200
    assert result.json()["code"] == "ADMIN_CREDENTIALS_CHANGED"
    assert current not in result.text and replacement not in result.text and "hash" not in result.text
    for session in [session_a, session_b]:
        rejected = client.get("/api/admin/profile", headers=session)
        assert rejected.status_code == 401
        assert rejected.json()["detail"]["code"] == "AUTH_SESSION_REVOKED"
    assert login(client, current).status_code == 401
    assert login(client, new_password, new_username).status_code == 200
    with factory() as db:
        admin = db.get(AdminUser, 1)
        assert admin.auth_version == 2
        assert admin.username == new_username
        assert admin.password_hash != new_password
        assert verify_password(new_password, admin.password_hash)
        assert (admin.password_hash == previous_hash) == (mode == "username")


def test_wrong_current_password_preserves_account(credential_env):
    client, factory, (current, _, previous_hash) = credential_env
    session = headers(client, current)
    response = client.patch("/api/admin/credentials", headers=session, json={"current_password": secrets.token_urlsafe(24), "new_username": "renamed"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CURRENT_PASSWORD_INCORRECT"
    assert client.get("/api/me", headers=session).status_code == 200
    with factory() as db:
        admin = db.get(AdminUser, 1)
        assert (admin.username, admin.password_hash, admin.auth_version) == ("testadmin", previous_hash, 1)


@pytest.mark.parametrize("case", ["missing_current", "empty_current", "no_changes", "short_name", "long_name", "chinese", "space", "dot", "dash", "digit_start", "short_password", "long_password", "confirmation", "extra"])
def test_invalid_credentials_inputs(credential_env, case):
    client, _, (current, replacement, _) = credential_env
    payload = {"current_password": current, "new_username": "renamed"}
    if case == "missing_current":
        payload.pop("current_password")
    elif case == "empty_current":
        payload["current_password"] = ""
    elif case == "no_changes":
        payload.pop("new_username")
    elif case in {"short_name", "long_name", "chinese", "space", "dot", "dash", "digit_start"}:
        payload["new_username"] = {"short_name": "ab", "long_name": "a" * 65, "chinese": "管理员", "space": "admin name", "dot": "admin.name", "dash": "admin-name", "digit_start": "1admin"}[case]
    elif case in {"short_password", "long_password"}:
        payload["new_password"] = secrets.token_urlsafe(4) if case == "short_password" else secrets.token_urlsafe(130)
    elif case == "confirmation":
        payload.update(new_password=replacement, confirm_new_password=current)
    else:
        payload["auth_version"] = 100
    result = client.patch("/api/admin/credentials", headers=headers(client, current), json=payload)
    assert result.status_code == 422
    assert current not in result.text and replacement not in result.text


def test_username_conflict_and_unchanged_value(credential_env):
    client, factory, (current, _, previous_hash) = credential_env
    with factory() as db:
        db.add(AdminUser(username="occupied", password_hash=previous_hash))
        db.commit()
    session = headers(client, current)
    conflict = client.patch("/api/admin/credentials", headers=session, json={"current_password": current, "new_username": "occupied"})
    assert conflict.status_code == 409
    unchanged = client.patch("/api/admin/credentials", headers=session, json={"current_password": current, "new_username": "testadmin"})
    assert unchanged.status_code == 400
    assert client.get("/api/me", headers=session).status_code == 200


def test_database_failure_rolls_back_all_fields(credential_env, monkeypatch):
    client, factory, (current, replacement, previous_hash) = credential_env
    session = headers(client, current)
    def failed_commit(self):
        raise RuntimeError("simulated transaction failure")
    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", failed_commit)
        response = client.patch("/api/admin/credentials", headers=session, json={"current_password": current, "new_username": "renamed", "new_password": replacement})
    assert response.status_code == 500
    assert "simulated" not in response.text
    with factory() as db:
        admin = db.get(AdminUser, 1)
        assert (admin.username, admin.password_hash, admin.auth_version) == ("testadmin", previous_hash, 1)
    assert client.get("/api/me", headers=session).status_code == 200


def test_hash_failure_preserves_account(credential_env, monkeypatch):
    client, factory, (current, replacement, previous_hash) = credential_env
    def failed_hash(_password):
        raise RuntimeError("simulated hash failure")
    monkeypatch.setattr("app.services.admin_service.hash_password", failed_hash)
    response = client.patch("/api/admin/credentials", headers=headers(client, current), json={"current_password": current, "new_password": replacement})
    assert response.status_code == 500
    with factory() as db:
        admin = db.get(AdminUser, 1)
        assert admin.password_hash == previous_hash and admin.auth_version == 1


@pytest.mark.parametrize("kind", ["no_version", "old_version", "boolean_version", "expired", "invalid_signature", "missing_exp"])
def test_invalid_and_old_tokens(credential_env, kind):
    client, _, _ = credential_env
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": "1", "iat": now, "exp": now + timedelta(minutes=10), "auth_version": 1}
    if kind == "no_version":
        payload.pop("auth_version")
    elif kind == "old_version":
        payload["auth_version"] = 0
    elif kind == "boolean_version":
        payload["auth_version"] = True
    elif kind == "expired":
        payload["exp"] = now - timedelta(minutes=10)
    elif kind == "missing_exp":
        payload.pop("exp")
    key = secrets.token_urlsafe(48) if kind == "invalid_signature" else settings.jwt_secret_key
    token = jwt.encode(payload, key, algorithm=settings.jwt_algorithm)
    response = client.get("/api/admin/profile", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_SESSION_REVOKED"
    assert token not in response.text


def test_stale_concurrent_update_is_rejected(credential_env):
    _, factory, (current, replacement, _) = credential_env
    with factory() as first, factory() as second:
        admin_a, admin_b = first.get(AdminUser, 1), second.get(AdminUser, 1)
        change_credentials(first, admin_a, CredentialsRequest(current_password=current, new_username="firstwinner"))
        with pytest.raises(CredentialsError) as error:
            change_credentials(second, admin_b, CredentialsRequest(current_password=current, new_password=replacement))
        assert error.value.code == "AUTH_SESSION_REVOKED"
    with factory() as db:
        admin = db.get(AdminUser, 1)
        assert admin.username == "firstwinner" and admin.auth_version == 2
        assert verify_password(current, admin.password_hash)


def test_bootstrap_does_not_resurrect_renamed_admin(credential_env):
    _, factory, (current, _, _) = credential_env
    settings = Settings(_env_file=None, bootstrap_admin_username="testadmin", bootstrap_admin_password=current)
    with factory() as db:
        admin = db.get(AdminUser, 1)
        change_credentials(db, admin, CredentialsRequest(current_password=current, new_username="renamed"))
    with factory() as db:
        ensure_bootstrap_admin(db, settings)
        assert db.scalars(select(AdminUser.username)).all() == ["renamed"]


def test_additive_migration_is_idempotent_and_preserves_data(tmp_path, monkeypatch):
    import app.database.session as database
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite'}", hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE admin_users (id INTEGER PRIMARY KEY, username VARCHAR(64) UNIQUE, password_hash VARCHAR(255))"))
        connection.execute(text("INSERT INTO admin_users (id, username, password_hash) VALUES (1, 'existing', 'opaque-placeholder')"))
    monkeypatch.setattr(database, "engine", engine)
    database._apply_lightweight_dev_migrations()
    database._apply_lightweight_dev_migrations()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT username, password_hash, auth_version FROM admin_users")).one() == ("existing", "opaque-placeholder", 1)
    assert "auth_version" in {column["name"] for column in inspect(engine).get_columns("admin_users")}
    engine.dispose()


def test_credential_events_do_not_log_secrets(credential_env):
    import io
    import logging
    from app.config.logging import APP_LOGGER_NAME

    client, _, (current, replacement, previous_hash) = credential_env
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        session = headers(client, current)
        client.patch("/api/admin/credentials", headers=session, json={"current_password": replacement, "new_username": "renamed"})
        client.patch("/api/admin/credentials", headers=session, json={"current_password": current, "new_username": "renamed", "new_password": replacement})
        client.get("/api/admin/profile", headers=session)
        recorded = stream.getvalue()
        assert "Admin credentials changed" in recorded
        assert "Admin credentials change failed" in recorded
        assert "Revoked admin session rejected" in recorded
        assert all(value not in recorded for value in [current, replacement, previous_hash, session["Authorization"]])
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def test_database_engine_hides_bound_parameters():
    from app.database.session import build_engine
    engine = build_engine(Settings(_env_file=None, database_url="sqlite:///:memory:"))
    assert engine.hide_parameters is True
    engine.dispose()
