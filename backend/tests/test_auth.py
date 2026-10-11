def test_login_and_protected_me_endpoint(tmp_path, monkeypatch):
    database_path = tmp_path / "auth.sqlite"
    monkeypatch.setenv("EMAIL_DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("EMAIL_JWT_SECRET_KEY", "auth-test-secret-32-bytes-long-value")

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.main import app
    from app.models import AdminUser, Base
    from app.routers.auth import get_db
    from app.utils.security import hash_password

    test_engine = create_engine(f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(test_engine)
    db = TestSession()
    db.add(AdminUser(username="admin", password_hash=hash_password("correct-password")))
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
            bad = client.post("/api/login", json={"username": "admin", "password": "bad"})
            assert bad.status_code == 401
            assert "database" not in bad.text.lower()

            login = client.post(
                "/api/login",
                json={"username": "admin", "password": "correct-password"},
            )
            assert login.status_code == 200
            token = login.json()["access_token"]

            me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200
            assert me.json() == {"id": 1, "username": "admin"}

            unauthorized = client.get("/api/me")
            assert unauthorized.status_code == 401
    finally:
        app.dependency_overrides.clear()
