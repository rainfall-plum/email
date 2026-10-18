from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_mailbox_listing_filters_paginates_and_sorts(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", "listing-test-secret-32-bytes")
    engine = create_engine(f"sqlite:///{(tmp_path / 'listing.sqlite').as_posix()}")
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from app.main import app
    from app.models import AdminUser, Base, Email, Mailbox, Tag
    from app.routers.auth import get_db
    from app.utils.security import hash_password

    Base.metadata.create_all(engine)
    db = session_factory()
    urgent = Tag(name="urgent")
    review = Tag(name="review")
    first = Mailbox(email_address="first@example.test", local_part="first", display_name="First Name", tags=[urgent])
    second = Mailbox(email_address="second@example.test", local_part="second", display_name="Second User", tags=[urgent, review])
    third = Mailbox(email_address="third@example.test", local_part="third")
    db.add_all([AdminUser(username="admin", password_hash=hash_password("pw")), urgent, review, first, second, third])
    db.flush()
    db.add_all([
        Email(mailbox_id=first.id, sender="a@example.com", receiver=first.email_address, is_read=False, received_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        Email(mailbox_id=second.id, sender="b@example.com", receiver=second.email_address, is_read=True, received_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
    ])
    db.commit()
    urgent_id, review_id = urgent.id, review.id
    db.close()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            token = client.post("/api/login", json={"username": "admin", "password": "pw"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            any_result = client.get(f"/api/mailboxes?tag_ids={urgent_id}&tag_ids={review_id}&tag_mode=any", headers=headers).json()
            assert any_result["total"] == 2
            all_result = client.get(f"/api/mailboxes?tag_ids={urgent_id}&tag_ids={review_id}&tag_mode=all", headers=headers).json()
            assert [item["email_address"] for item in all_result["items"]] == ["second@example.test"]
            untagged = client.get("/api/mailboxes?untagged=true", headers=headers).json()
            assert [item["email_address"] for item in untagged["items"]] == ["third@example.test"]
            paged = client.get("/api/mailboxes?page=1&page_size=1&sort_by=latest_email_desc", headers=headers).json()
            assert paged["total"] == 3 and paged["pages"] == 3
            assert paged["items"][0]["email_address"] == "second@example.test"
            assert paged["items"][0]["email_count"] == 1
            assert paged["items"][0]["unread_count"] == 0
            by_name = client.get("/api/mailboxes?search=second", headers=headers).json()
            assert [item["email_address"] for item in by_name["items"]] == ["second@example.test"]
            by_address = client.get("/api/mailboxes?search=FIRST%40EXAMPLE", headers=headers).json()
            assert [item["email_address"] for item in by_address["items"]] == ["first@example.test"]
            wildcard_literal = client.get("/api/mailboxes?search=%25", headers=headers).json()
            assert wildcard_literal["total"] == 0
            assert client.get("/api/mailboxes?sort_by=invalid", headers=headers).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_system_settings_expose_safe_values_and_update_allowlist(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", "settings-test-secret-32-bytes")
    engine = create_engine(f"sqlite:///{(tmp_path / 'settings.sqlite').as_posix()}")
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from app.main import app
    from app.models import AdminUser, Base
    from app.routers.auth import get_db
    from app.utils.security import hash_password

    Base.metadata.create_all(engine)
    db = session_factory()
    db.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db.commit(); db.close()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            token = client.post("/api/login", json={"username": "admin", "password": "pw"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            settings = client.get("/api/settings", headers=headers).json()
            assert {item["key"] for item in settings} == {"allowed_domain", "max_emails_per_mailbox", "access_token_expire_minutes", "environment"}
            assert all("jwt" not in item["key"].lower() for item in settings)
            updated = client.put("/api/settings/max_emails_per_mailbox", headers=headers, json={"value": "20"})
            assert updated.status_code == 200 and updated.json()["value"] == "20"
            assert client.put("/api/settings/max_emails_per_mailbox", headers=headers, json={"value": "0"}).status_code == 400
            assert client.put("/api/settings/allowed_domain", headers=headers, json={"value": "bad.test"}).status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_dashboard_stats_are_aggregated(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", "dashboard-test-secret-32-bytes")
    engine = create_engine(f"sqlite:///{(tmp_path / 'dashboard.sqlite').as_posix()}")
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from app.main import app
    from app.models import AdminUser, Base, Email, Mailbox, Tag
    from app.routers.auth import get_db
    from app.utils.security import hash_password

    Base.metadata.create_all(engine)
    db = session_factory()
    mailbox = Mailbox(email_address="stats@example.test", local_part="stats")
    db.add_all([AdminUser(username="admin", password_hash=hash_password("pw")), Tag(name="ops"), mailbox])
    db.flush()
    db.add_all([
        Email(mailbox_id=mailbox.id, sender="a@example.com", receiver=mailbox.email_address, is_read=False, received_at=datetime.now(timezone.utc)),
        Email(mailbox_id=mailbox.id, sender="b@example.com", receiver=mailbox.email_address, is_read=True, received_at=datetime.now(timezone.utc)),
    ])
    db.commit(); db.close()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            token = client.post("/api/login", json={"username": "admin", "password": "pw"}).json()["access_token"]
            result = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
            assert result.status_code == 200
            assert result.json() == {"mailbox_count": 1, "email_count": 2, "unread_email_count": 1, "tag_count": 1}
    finally:
        app.dependency_overrides.clear()
