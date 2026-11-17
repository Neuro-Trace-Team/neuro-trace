import json

from sqlalchemy import create_engine

from src.db import sessions
from src.main import RustFSStorage, live, ready


def test_live_does_not_require_dependencies() -> None:
    assert live() == {"status": "ok"}


def test_ready_reports_all_available_dependencies(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    monkeypatch.setattr(sessions, "auth_engine", engine)
    monkeypatch.setattr(sessions, "medical_engine", engine)
    monkeypatch.setattr(sessions, "audit_engine", engine)
    monkeypatch.setattr(RustFSStorage, "check_available", lambda self: None)

    response = ready()

    assert response == {
        "status": "ready",
        "dependencies": {
            "auth_db": "ok",
            "medical_db": "ok",
            "audit_db": "ok",
            "rustfs": "ok",
        },
    }


def test_ready_returns_503_when_a_database_is_unavailable(monkeypatch) -> None:
    healthy_engine = create_engine("sqlite://")
    broken_engine = create_engine("postgresql://user:password@127.0.0.1:1/unavailable", connect_args={"connect_timeout": 1})
    monkeypatch.setattr(sessions, "auth_engine", healthy_engine)
    monkeypatch.setattr(sessions, "medical_engine", broken_engine)
    monkeypatch.setattr(sessions, "audit_engine", healthy_engine)
    monkeypatch.setattr(RustFSStorage, "check_available", lambda self: None)

    response = ready()

    assert response.status_code == 503
    assert json.loads(response.body)["dependencies"] == {
        "auth_db": "ok",
        "medical_db": "unavailable",
        "audit_db": "ok",
        "rustfs": "ok",
    }
