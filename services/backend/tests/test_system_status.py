from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine

from src.api.v1 import admin
from src.db import sessions
from src.schemas.system_status import BackendStatus, ComponentStatus, ConnectionStatus, ExternalServiceStatus
from src.services import system_status
from src.services.storage import ObjectStorageError


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
    monkeypatch.setattr(
        system_status,
        "RustFSStorage",
        lambda: SimpleNamespace(check_available=lambda: None),
    )
    monkeypatch.setattr(system_status, "completion_consumer_status", lambda: "up")

    backend, databases, preprocessing, ml = system_status.system_status()

    assert backend.status == "up"
    assert {name: item.status for name, item in backend.connections.items()} == {
        "rustfs": "up", "rabbitmq_consumer": "up",
    }
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


@pytest.mark.parametrize("failed_connection", ["rustfs", "rabbitmq_consumer"])
def test_backend_connection_failure_keeps_complete_diagnostics(monkeypatch, failed_connection: str) -> None:
    if failed_connection == "rustfs":
        class UnavailableStorage:
            def check_available(self) -> None:
                raise ObjectStorageError("offline")

        monkeypatch.setattr(system_status, "RustFSStorage", UnavailableStorage)
        monkeypatch.setattr(system_status, "completion_consumer_status", lambda: "up")
    else:
        monkeypatch.setattr(
            system_status,
            "RustFSStorage",
            lambda: SimpleNamespace(check_available=lambda: None),
        )
        monkeypatch.setattr(system_status, "completion_consumer_status", lambda: "down")

    monkeypatch.setattr(
        system_status,
        "database_statuses",
        lambda: {
            "auth_db": ComponentStatus(status="up"),
            "medical_db": ComponentStatus(status="up"),
            "audit_db": ComponentStatus(status="up"),
        },
    )
    monkeypatch.setattr(
        system_status,
        "get_settings",
        lambda: SimpleNamespace(preprocessing_url="http://preprocessing.test", ml_url="http://ml.test"),
    )
    monkeypatch.setattr(
        system_status,
        "external_service_status",
        lambda url: ExternalServiceStatus(
            status="ok",
            connections={"diagnostic": system_status.ExternalConnectionStatus(status="up")},
        ),
    )

    backend, databases, preprocessing, ml = system_status.system_status()

    assert set(backend.connections) == {"rustfs", "rabbitmq_consumer"}
    assert backend.connections[failed_connection].status == "down"
    assert backend.connections[
        "rabbitmq_consumer" if failed_connection == "rustfs" else "rustfs"
    ].status == "up"
    assert set(databases) == {"auth_db", "medical_db", "audit_db"}
    assert preprocessing.status == "ok"
    assert ml.status == "ok"


@pytest.mark.parametrize("connection_status", ["down", "unknown"])
def test_backend_connection_not_up_degrades_overall_status(monkeypatch, connection_status: str) -> None:
    backend = BackendStatus(
        status="up",
        connections={
            "rustfs": ConnectionStatus(status=connection_status),
            "rabbitmq_consumer": ConnectionStatus(status="up"),
        },
    )
    monkeypatch.setattr(
        admin.system_status_service,
        "system_status",
        lambda: (
            backend,
            {"auth_db": ComponentStatus(status="up")},
            ExternalServiceStatus(status="ok"),
            ExternalServiceStatus(status="ok"),
        ),
    )

    response = admin.get_system_status()

    assert response.status == "degraded"
    assert response.backend.connections["rustfs"].status == connection_status
