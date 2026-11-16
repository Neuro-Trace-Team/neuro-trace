from types import SimpleNamespace

import httpx
from sqlalchemy import create_engine

from src.db import sessions
from src.services import system_status


def test_system_status_combines_backend_databases_and_existing_service_diagnostics(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    monkeypatch.setattr(sessions, "auth_engine", engine)
    monkeypatch.setattr(sessions, "medical_engine", engine)
    monkeypatch.setattr(sessions, "audit_engine", engine)
    monkeypatch.setattr(
        system_status,
        "get_settings",
        lambda: SimpleNamespace(
            preprocessing_url="http://preprocessing.test",
            ml_url="http://ml.test",
            service_timeout_seconds=1,
        ),
    )

    def get(url: str, **kwargs):
        if url.endswith("/health/connections"):
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "connections": {
                        "rustfs": {"status": "ok", "latency_ms": 1.2, "error": None},
                        "rabbitmq": {"status": "ok", "latency_ms": 2.3, "error": None},
                    },
                },
                request=httpx.Request("GET", url),
            )
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "connections": {
                    "database": {"status": "up", "latency_ms": 3},
                    "rabbitmq_consumer": {"status": "up"},
                    "rabbitmq_publisher": {"status": "up"},
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(system_status.httpx, "get", get)

    databases, preprocessing, ml = system_status.system_status()

    assert {name: item.status for name, item in databases.items()} == {
        "auth_db": "up", "medical_db": "up", "audit_db": "up",
    }
    assert preprocessing.status == "ok"
    assert set(preprocessing.connections) == {"rustfs", "rabbitmq"}
    assert ml.status == "ok"
    assert set(ml.connections) == {"database", "rabbitmq_consumer", "rabbitmq_publisher"}


def test_unreachable_external_service_is_reported_down(monkeypatch) -> None:
    monkeypatch.setattr(
        system_status,
        "get_settings",
        lambda: SimpleNamespace(service_timeout_seconds=1),
    )
    monkeypatch.setattr(
        system_status.httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline")),
    )

    result = system_status.external_service_status("http://service.test/connections")

    assert result.status == "down"
    assert result.connections == {}
