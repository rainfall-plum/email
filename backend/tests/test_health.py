def test_health_endpoint(temporary_database):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(response.headers["X-Request-ID"]) == 32
