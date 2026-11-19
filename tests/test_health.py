from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_check_when_database_is_unavailable(monkeypatch):
    from app import main

    def raise_database_error():
        raise ServerSelectionTimeoutError("MongoDB unavailable")

    monkeypatch.setattr(
        main,
        "check_database_connection",
        raise_database_error,
    )

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "status": "unhealthy",
            "database": "unavailable",
        }
    }
