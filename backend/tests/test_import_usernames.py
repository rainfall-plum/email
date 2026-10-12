import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings
from app.database.session import get_db
from app.models import AdminUser, Base, ImportUsername, Mailbox
from app.routers.auth import get_current_admin
from app.routers.mailboxes import router
from app.services.username_import_service import (
    MAX_IMPORT_BYTES, UsernameImportError, import_usernames, parse_username_file,
)


@pytest.fixture
def import_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'import.sqlite').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    names_dir = tmp_path / "names"
    names_dir.mkdir()
    pools = {"available_first": ["alice", "bob"], "available_last": ["wang", "li"],
             "used_first": ["old", "former"], "used_last": ["name"]}
    for name, values in pools.items():
        (names_dir / f"{name}_names.json").write_text(json.dumps(values), encoding="utf-8")
    settings = Settings(names_dir=names_dir, allowed_domain="example.test")
    admin = AdminUser(username="importadmin", password_hash="not-a-login-hash")
    session.add(admin)
    session.commit()
    yield session, settings, admin
    session.close()
    engine.dispose()


@pytest.mark.parametrize("content,code", [
    (b'{}', "unsupported_structure"),
    (b'{"usernames":"alice"}', "unsupported_structure"),
    (b'{"usernames":[]}', "unsupported_structure"),
    (b'{"usernames":["alice"],"domain":"override.test"}', "unsupported_structure"),
    (b'["alice"]', "unsupported_structure"),
    (b'{broken', "invalid_json"),
    (b'\xff', "invalid_json"),
    (b'{"usernames":[NaN]}', "invalid_json"),
    (b'{"usernames":["a"],"usernames":["b"]}', "invalid_json"),
    (b' ' * (MAX_IMPORT_BYTES + 1), "file_too_large"),
    (json.dumps({"usernames": ["a"] * 1001}).encode(), "too_many_usernames"),
], ids=lambda value: f"bytes-{len(value)}" if isinstance(value, bytes) else value)
def test_parse_rejects_invalid_inputs(content, code):
    with pytest.raises(UsernameImportError) as error:
        parse_username_file("names.json", content)
    assert error.value.code == code


def test_parse_standard_and_extension():
    assert parse_username_file("names.JSON", b'{"usernames":["lower","123","mail88"]}') == ["lower", "123", "mail88"]
    with pytest.raises(UsernameImportError) as error:
        parse_username_file("names.txt", b'{"usernames":["lower"]}')
    assert error.value.code == "invalid_extension"


@pytest.mark.parametrize("username,reason", [
    ("中文", "invalid_format"), ("Upper", "invalid_format"), ("a.b", "invalid_format"),
    ("a-b", "invalid_format"), ("a_b", "invalid_format"), ("", "empty_username"),
    (" a", "invalid_format"), ("a ", "invalid_format"), ("a" * 65, "too_long"),
    (None, "invalid_format"), (123, "invalid_format"), ({"nested": "data"}, "invalid_format"),
    ("a\n", "invalid_format"), ("a b", "invalid_format"),
])
def test_username_validation(import_db, username, reason):
    db, settings, admin = import_db
    result = import_usernames(db, settings, [username], admin.id)
    assert result["success_count"] == 0
    assert result["invalid_count"] == 1
    assert result["rejected_usernames"][0]["reason"] == reason


def test_import_statistics_uniqueness_domain_and_pool_compatibility(import_db):
    db, settings, admin = import_db
    snapshots = {path.name: path.read_bytes() for path in settings.names_dir.iterdir()}
    existing = Mailbox(local_part="exists", email_address="exists@example.test")
    db.add(existing)
    db.commit()
    result = import_usernames(db, settings, ["lower", "123", "mail88", "lower", "alice", "alicewang", "old", "formername", "exists", "a.b"], admin.id)
    assert (result["total"], result["success_count"], result["duplicate_count"], result["existing_count"], result["invalid_count"]) == (10, 3, 1, 5, 1)
    assert all(row["email"].endswith("@example.test") for row in result["created_mailboxes"])
    assert {row["reason"] for row in result["rejected_usernames"]} == {"duplicate_in_file", "already_available", "already_used", "already_exists", "invalid_format"}
    assert db.query(Mailbox).count() == 4
    assert db.query(ImportUsername).count() == 3
    repeated = import_usernames(db, settings, ["lower", "123", "mail88"], admin.id)
    assert repeated["success_count"] == 0 and repeated["existing_count"] == 3
    assert snapshots == {path.name: path.read_bytes() for path in settings.names_dir.iterdir()}
    db.add(Mailbox(local_part="lower", email_address="different@example.test"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_deleted_import_remains_used(import_db):
    db, settings, admin = import_db
    import_usernames(db, settings, ["remainused"], admin.id)
    db.delete(db.scalar(select(Mailbox).where(Mailbox.local_part == "remainused")))
    db.commit()
    result = import_usernames(db, settings, ["remainused"], admin.id)
    assert result["rejected_usernames"][0]["reason"] == "already_used"


def test_database_failure_rolls_back_mailbox_and_ledger(import_db, monkeypatch):
    db, settings, admin = import_db
    def fail_commit():
        raise RuntimeError("injected database failure")
    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(UsernameImportError) as error:
        import_usernames(db, settings, ["firstnew", "secondnew"], admin.id)
    assert error.value.code == "import_failed"
    assert db.query(Mailbox).count() == 0
    assert db.query(ImportUsername).count() == 0


def test_pool_failure_creates_no_mailboxes(import_db, monkeypatch):
    from app.utils.name_library import NameLibrary, NameLibraryError
    db, settings, admin = import_db
    def fail_read(*_, **kwargs):
        raise NameLibraryError("injected pool failure")
    monkeypatch.setattr(NameLibrary, "_read", fail_read)
    with pytest.raises(UsernameImportError):
        import_usernames(db, settings, ["firstnew"], admin.id)
    assert db.query(Mailbox).count() == 0


def test_import_does_not_update_component_pools(import_db, monkeypatch):
    from app.utils.name_library import NameLibrary
    db, settings, admin = import_db
    def forbidden_write(*_):
        raise AssertionError("complete username imports must not mutate component pools")
    monkeypatch.setattr(NameLibrary, "_write", forbidden_write)
    assert import_usernames(db, settings, ["independent"], admin.id)["success_count"] == 1


def test_upload_api_limits_requires_admin_and_returns_safe_errors(import_db, monkeypatch):
    db, settings, admin = import_db
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr("app.routers.mailboxes.get_settings", lambda: settings)
    with TestClient(app) as client:
        assert client.post("/api/mailboxes/import-usernames", files={"file": ("names.json", b'{}')}).status_code == 401
        app.dependency_overrides[get_current_admin] = lambda: admin
        for filename, content, code in [("n.txt", b'{}', "invalid_extension"), ("n.json", b'\xff', "invalid_json"), ("n.json", b' ' * (MAX_IMPORT_BYTES + 1), "file_too_large")]:
            response = client.post("/api/mailboxes/import-usernames", files={"file": (filename, content)})
            assert response.status_code in {400, 413}
            assert response.json()["detail"]["code"] == code
        response = client.post("/api/mailboxes/import-usernames", files={"file": ("n.json", b'{"usernames":["apimail","apimail","invalid.name"]}')})
        assert response.status_code == 200
        assert response.json()["success_count"] == 1
        assert response.json()["duplicate_count"] == 1
        assert response.json()["invalid_count"] == 1


def test_batch_pool_write_failure_rolls_back_database_and_restores_files(import_db, monkeypatch):
    from app.services.mailbox_service import generate_mailboxes
    from app.utils.name_library import NameLibrary, NameLibraryError
    db, settings, _ = import_db
    snapshot = {path.name: path.read_bytes() for path in settings.names_dir.iterdir()}
    original = NameLibrary._write
    failed = False
    def fail_once(self, state, kind, values):
        nonlocal failed
        if state == "used" and kind == "first" and not failed:
            failed = True
            raise NameLibraryError("injected pool write failure")
        return original(self, state, kind, values)
    monkeypatch.setattr(NameLibrary, "_write", fail_once)
    with pytest.raises(NameLibraryError):
        generate_mailboxes(db, settings, 1, [])
    assert db.query(Mailbox).count() == 0
    assert {path.name: json.loads(path.read_text()) for path in settings.names_dir.iterdir()} == {name: json.loads(content) for name, content in snapshot.items()}


def test_batch_commit_failure_restores_pools(import_db, monkeypatch):
    from app.services.mailbox_service import MailboxServiceError, generate_mailboxes
    db, settings, _ = import_db
    snapshot = {path.name: json.loads(path.read_text()) for path in settings.names_dir.iterdir()}
    def fail_commit():
        raise RuntimeError("injected commit failure")
    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(MailboxServiceError):
        generate_mailboxes(db, settings, 1, [])
    assert db.query(Mailbox).count() == 0
    assert {path.name: json.loads(path.read_text()) for path in settings.names_dir.iterdir()} == snapshot


def test_streamed_upload_size_limit_before_multipart_parsing():
    import asyncio
    from app.main import ImportBodyLimitMiddleware
    entered = False
    sent = []
    parts = iter([
        {"type": "http.request", "body": b"a" * (700 * 1024), "more_body": True},
        {"type": "http.request", "body": b"a" * (500 * 1024), "more_body": False},
    ])
    async def downstream(scope, receive, send):
        nonlocal entered
        entered = True
    async def receive():
        return next(parts)
    async def send(message):
        sent.append(message)
    asyncio.run(ImportBodyLimitMiddleware(downstream)(
        {"type": "http", "path": "/api/mailboxes/import-usernames", "headers": []}, receive, send))
    assert not entered
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["detail"]["code"] == "file_too_large"
