from src.main import app
from fastapi.testclient import TestClient
from uuid import uuid4


client = TestClient(app)


def test_openapi_exposes_current_examination_contract() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/examinations/{examination_id}/preprocessing-status" in paths
    assert "/api/v1/examinations/{examination_id}/results" in paths
    assert "get" in paths["/api/v1/examinations/{examination_id}/results"]
    assert "post" not in paths["/api/v1/examinations/{examination_id}/results"]


def test_openapi_does_not_reintroduce_removed_resources() -> None:
    paths = app.openapi()["paths"]
    forbidden = ("preprocessing-jobs", "/analyses", "pain-assessments", "/channels", "eeg-channels", "/internal/")
    assert not [path for path in paths if any(fragment in path for fragment in forbidden)]


def test_openapi_contains_exactly_the_supported_backend_operations() -> None:
    operations = {(path, method.upper()) for path, item in app.openapi()["paths"].items() for method in item if method in {"get", "post", "patch", "put", "delete"}}
    expected = {
        ("/health/live", "GET"), ("/health/ready", "GET"),
        ("/api/v1/auth/login", "POST"), ("/api/v1/auth/refresh", "POST"), ("/api/v1/auth/logout", "POST"), ("/api/v1/auth/me", "GET"), ("/api/v1/auth/forgot-password", "POST"), ("/api/v1/auth/reset-password", "POST"), ("/api/v1/auth/change-password", "POST"),
        ("/api/v1/users", "GET"), ("/api/v1/users", "POST"), ("/api/v1/users/me", "GET"), ("/api/v1/users/me", "PATCH"), ("/api/v1/users/{user_id}", "GET"), ("/api/v1/users/{user_id}", "PATCH"),
        ("/api/v1/patients", "POST"), ("/api/v1/patients", "GET"), ("/api/v1/patients/stats", "GET"), ("/api/v1/patients/{patient_id}", "GET"), ("/api/v1/patients/{patient_id}/stats", "GET"), ("/api/v1/patients/{patient_id}/examinations", "GET"),
        ("/api/v1/examinations", "POST"), ("/api/v1/examinations", "GET"), ("/api/v1/examinations/{examination_id}", "GET"), ("/api/v1/examinations/{examination_id}", "PATCH"), ("/api/v1/examinations/{examination_id}", "DELETE"), ("/api/v1/examinations/{examination_id}/preprocessing-status", "GET"), ("/api/v1/examinations/{examination_id}/results", "GET"), ("/api/v1/examinations/{examination_id}/events", "GET"), ("/api/v1/examinations/{examination_id}/events", "POST"), ("/api/v1/examinations/{examination_id}/events/{event_id}", "PATCH"), ("/api/v1/examinations/{examination_id}/events/{event_id}", "DELETE"),
        ("/api/v1/examinations/bulk-delete", "POST"), ("/api/v1/examinations/bulk-export", "POST"), ("/api/v1/admin/audit-logs", "GET"), ("/api/v1/admin/audit-logs/{log_id}", "GET"),
    }
    assert expected <= operations


def test_every_protected_endpoint_rejects_anonymous_frontend_client() -> None:
    uid = str(uuid4())
    requests = [
        ("GET", "/api/v1/auth/me", {}), ("POST", "/api/v1/auth/logout", {"json": {"refresh_token": "x"}}), ("POST", "/api/v1/auth/change-password", {"json": {"current_password": "x", "new_password": "ValidPassword123!"}}),
        ("GET", "/api/v1/users", {}), ("POST", "/api/v1/users", {"json": {"email": "a@b.com", "password": "ValidPassword123!", "first_name": "A", "last_name": "B", "role": "DOCTOR"}}), ("GET", "/api/v1/users/me", {}), ("PATCH", "/api/v1/users/me", {"json": {"first_name": "A"}}), ("GET", f"/api/v1/users/{uid}", {}), ("PATCH", f"/api/v1/users/{uid}", {"json": {"is_active": False}}),
        ("POST", "/api/v1/patients", {}), ("GET", "/api/v1/patients", {}), ("GET", "/api/v1/patients/stats", {}), ("GET", f"/api/v1/patients/{uid}", {}), ("GET", f"/api/v1/patients/{uid}/stats", {}), ("GET", f"/api/v1/patients/{uid}/examinations", {}),
        ("POST", "/api/v1/examinations", {"data": {"patient_id": uid}, "files": {"file": ("test.eeg", b"x")}}), ("GET", "/api/v1/examinations", {}), ("GET", f"/api/v1/examinations/{uid}", {}), ("PATCH", f"/api/v1/examinations/{uid}", {"json": {"examination_date": None}}), ("DELETE", f"/api/v1/examinations/{uid}", {}), ("GET", f"/api/v1/examinations/{uid}/preprocessing-status", {}), ("GET", f"/api/v1/examinations/{uid}/results", {}), ("GET", f"/api/v1/examinations/{uid}/events", {}), ("POST", f"/api/v1/examinations/{uid}/events", {"json": {"timestamp": 1, "type": "stimulus"}}), ("PATCH", f"/api/v1/examinations/{uid}/events/{uid}", {"json": {"description": "x"}}), ("DELETE", f"/api/v1/examinations/{uid}/events/{uid}", {}),
        ("POST", "/api/v1/examinations/bulk-delete", {"json": {"examination_ids": [uid]}}), ("POST", "/api/v1/examinations/bulk-export", {"json": {"examination_ids": [uid]}}), ("GET", "/api/v1/admin/audit-logs", {}), ("GET", f"/api/v1/admin/audit-logs/{uid}", {}),
    ]
    for method, path, kwargs in requests:
        response = client.request(method, path, **kwargs)
        assert response.status_code == 401, f"{method} {path}: {response.status_code} {response.text}"
