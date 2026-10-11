from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_mailbox_and_tag_api_requires_admin_and_supports_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", "mailbox-api-test-secret-32-bytes")
    database_path = tmp_path / "api.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.main import app
    from app.models import AdminUser, Base
    from app.routers.auth import get_db
    from app.utils.security import hash_password

    Base.metadata.create_all(engine)
    db = TestSession()
    db.add(AdminUser(username="admin3", password_hash=hash_password("password-3")))
    db.commit()
    db.close()

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            assert client.get("/api/mailboxes").status_code == 401
            login = client.post(
                "/api/login", json={"username": "admin3", "password": "password-3"}
            )
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            tag = client.post("/api/tags", headers=headers, json={"name": "验证码"})
            assert tag.status_code == 201
            tag_id = tag.json()["id"]

            created = client.post(
                "/api/mailboxes",
                headers=headers,
                json={"local_part": "alicewang", "tag_ids": [tag_id]},
            )
            assert created.status_code == 201
            mailbox_id = created.json()["id"]
            assert created.json()["email_address"].endswith("@example.test")
            assert created.json()["tag_ids"] == [tag_id]

            detail = client.get(f"/api/mailboxes/{mailbox_id}", headers=headers)
            assert detail.status_code == 200
            assert detail.json()["tag_ids"] == [tag_id]

            renamed = client.put(
                f"/api/tags/{tag_id}", headers=headers, json={"name": "renamed"}
            )
            assert renamed.status_code == 200
            detail_after_rename = client.get(
                f"/api/mailboxes/{mailbox_id}", headers=headers
            )
            assert detail_after_rename.json()["tag_ids"] == [tag_id]

            updated = client.put(
                f"/api/mailboxes/{mailbox_id}", headers=headers, json={"tag_ids": []}
            )
            assert updated.status_code == 200
            assert updated.json()["tag_ids"] == []

            duplicate = client.post(
                "/api/mailboxes", headers=headers, json={"local_part": "alice.wang"}
            )
            assert duplicate.status_code == 422
            assert duplicate.json() == {"detail": "请求参数无效"}
            assert client.get("/api/mailboxes", headers=headers).json()[0]["id"] == mailbox_id

            assert client.delete(f"/api/mailboxes/{mailbox_id}", headers=headers).status_code == 204
            assert client.delete(f"/api/tags/{tag_id}", headers=headers).status_code == 204
    finally:
        app.dependency_overrides.clear()
