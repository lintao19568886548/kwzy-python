from fastapi.testclient import TestClient

import app.main as main_module
from app.main import create_app


def test_health() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "up"


def test_readiness_checks_database() -> None:
    client = TestClient(create_app())
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "up"}


def test_readiness_fails_closed_without_driver_details(monkeypatch) -> None:
    class BrokenSession:
        def execute(self, _statement) -> None:
            raise RuntimeError("password=must-not-leak")

        def close(self) -> None:
            return None

    monkeypatch.setattr(main_module, "SessionLocal", BrokenSession)
    client = TestClient(create_app())
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready", "database": "down"}
    assert "must-not-leak" not in resp.text
