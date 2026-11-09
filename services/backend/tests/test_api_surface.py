import json

from src.main import app
from fastapi.testclient import TestClient
from uuid import uuid4


client = TestClient(app)


def test_openapi_exposes_current_examination_contract() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/examinations/{examination_id}/preprocessing-status" in paths
    assert "/api/v1/examinations/{examination_id}/results" in paths
    assert "/api/v1/examinations/statuses" in paths
    assert "get" in paths["/api/v1/examinations/{examination_id}/results"]
    assert "post" not in paths["/api/v1/examinations/{examination_id}/results"]


def test_list_endpoints_expose_filtering_sorting_and_pagination_contracts() -> None:
    paths = app.openapi()["paths"]

    def parameters(path: str) -> dict[str, dict]:
        return {parameter["name"]: parameter for parameter in paths[path]["get"]["parameters"]}

    examination_parameters = parameters("/api/v1/examinations")
    assert {
        "page", "page_size", "query", "id", "patient_id", "uploaded_by", "status",
        "examination_date_from", "examination_date_to", "sort_by", "sort_order",
    } <= examination_parameters.keys()
    assert "ExaminationStatus" in json.dumps(examination_parameters["status"]["schema"])

    user_parameters = parameters("/api/v1/users")
    assert {
        "page", "page_size", "query", "id", "email", "first_name", "last_name",
        "role", "is_active", "sort_by", "sort_order",
    } <= user_parameters.keys()

    audit_parameters = parameters("/api/v1/admin/audit-logs")
    assert {
        "page", "page_size", "query", "id", "user_id", "type_id", "created_at_from",
        "created_at_to", "ip_address", "request_id", "resource_type", "resource_id",
        "sort_by", "sort_order",
    } <= audit_parameters.keys()


def test_openapi_does_not_reintroduce_removed_resources() -> None:
    paths = app.openapi()["paths"]
    forbidden = ("preprocessing-jobs", "/analyses", "pain-assessments", "/channels", "eeg-channels", "/events", "/internal/")
    assert not [path for path in paths if any(fragment in path for fragment in forbidden)]
    assert "/api/v1/auth/forgot-password" not in paths
    assert "/api/v1/auth/reset-password" not in paths


def test_openapi_contains_exactly_the_supported_backend_operations() -> None:
    operations = {(path, method.upper()) for path, item in app.openapi()["paths"].items() for method in item if method in {"get", "post", "patch", "put", "delete"}}
    expected = {
        ("/health/live", "GET"), ("/health/ready", "GET"),
        ("/api/v1/auth/login", "POST"), ("/api/v1/auth/refresh", "POST"), ("/api/v1/auth/logout", "POST"), ("/api/v1/auth/me", "GET"), ("/api/v1/auth/change-password", "POST"),
        ("/api/v1/users", "GET"), ("/api/v1/users", "POST"), ("/api/v1/users/me", "GET"), ("/api/v1/users/me", "PATCH"), ("/api/v1/users/{user_id}", "GET"), ("/api/v1/users/{user_id}", "PATCH"),
        ("/api/v1/me/recent/patients", "GET"), ("/api/v1/me/recent/examinations", "GET"),
        ("/api/v1/patients", "POST"), ("/api/v1/patients", "GET"), ("/api/v1/patients/stats", "GET"), ("/api/v1/patients/{patient_id}", "GET"), ("/api/v1/patients/{patient_id}/stats", "GET"), ("/api/v1/patients/{patient_id}/examinations", "GET"),
        ("/api/v1/examinations", "POST"), ("/api/v1/examinations", "GET"), ("/api/v1/examinations/statuses", "GET"), ("/api/v1/examinations/{examination_id}", "GET"), ("/api/v1/examinations/{examination_id}", "PATCH"), ("/api/v1/examinations/{examination_id}", "DELETE"), ("/api/v1/examinations/{examination_id}/preprocessing-status", "GET"), ("/api/v1/examinations/{examination_id}/results", "GET"),
        ("/api/v1/examinations/bulk-delete", "POST"), ("/api/v1/examinations/bulk-export", "POST"), ("/api/v1/admin/audit-logs", "GET"), ("/api/v1/admin/audit-logs/{log_id}", "GET"),
    }
    assert expected <= operations


def test_every_protected_endpoint_rejects_anonymous_frontend_client() -> None:
    uid = str(uuid4())
    requests = [
        ("GET", "/api/v1/auth/me", {}), ("POST", "/api/v1/auth/logout", {"json": {"refresh_token": "x"}}), ("POST", "/api/v1/auth/change-password", {"json": {"current_password": "x", "new_password": "ValidPassword123!"}}),
        ("GET", "/api/v1/users", {}), ("POST", "/api/v1/users", {"json": {"email": "a@b.com", "password": "ValidPassword123!", "first_name": "A", "last_name": "B", "role": "DOCTOR"}}), ("GET", "/api/v1/users/me", {}), ("PATCH", "/api/v1/users/me", {"json": {"first_name": "A"}}), ("GET", f"/api/v1/users/{uid}", {}), ("PATCH", f"/api/v1/users/{uid}", {"json": {"is_active": False}}),
        ("GET", "/api/v1/me/recent/patients", {}), ("GET", "/api/v1/me/recent/examinations", {}),
        ("POST", "/api/v1/patients", {}), ("GET", "/api/v1/patients", {}), ("GET", "/api/v1/patients/stats", {}), ("GET", f"/api/v1/patients/{uid}", {}), ("GET", f"/api/v1/patients/{uid}/stats", {}), ("GET", f"/api/v1/patients/{uid}/examinations", {}),
        ("POST", "/api/v1/examinations", {"data": {"patient_id": uid}, "files": {"file": ("test.eeg", b"x")}}), ("GET", "/api/v1/examinations", {}), ("GET", "/api/v1/examinations/statuses", {}), ("GET", f"/api/v1/examinations/{uid}", {}), ("PATCH", f"/api/v1/examinations/{uid}", {"json": {"examination_date": None}}), ("DELETE", f"/api/v1/examinations/{uid}", {}), ("GET", f"/api/v1/examinations/{uid}/preprocessing-status", {}), ("GET", f"/api/v1/examinations/{uid}/results", {}),
        ("POST", "/api/v1/examinations/bulk-delete", {"json": {"examination_ids": [uid]}}), ("POST", "/api/v1/examinations/bulk-export", {"json": {"examination_ids": [uid]}}), ("GET", "/api/v1/admin/audit-logs", {}), ("GET", f"/api/v1/admin/audit-logs/{uid}", {}),
    ]
    for method, path, kwargs in requests:
        response = client.request(method, path, **kwargs)
        assert response.status_code == 401, f"{method} {path}: {response.status_code} {response.text}"
