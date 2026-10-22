from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.db import sessions
from src.main import app


def test_live_does_not_require_dependencies() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_all_available_databases(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    monkeypatch.setattr(sessions, "auth_engine", engine)
    monkeypatch.setattr(sessions, "medical_engine", engine)
    monkeypatch.setattr(sessions, "audit_engine", engine)

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"auth_db": "ok", "medical_db": "ok", "audit_db": "ok"},
    }


def test_ready_returns_503_when_a_database_is_unavailable(monkeypatch) -> None:
    healthy_engine = create_engine("sqlite://")
    broken_engine = create_engine("postgresql://user:password@127.0.0.1:1/unavailable", connect_args={"connect_timeout": 1})
    monkeypatch.setattr(sessions, "auth_engine", healthy_engine)
    monkeypatch.setattr(sessions, "medical_engine", broken_engine)
    monkeypatch.setattr(sessions, "audit_engine", healthy_engine)

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"] == {
        "auth_db": "ok", "medical_db": "unavailable", "audit_db": "ok"
    }
