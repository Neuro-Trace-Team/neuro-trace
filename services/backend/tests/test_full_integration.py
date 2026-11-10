"""Run with NEUROTRACE_INTEGRATION=1 only against a fresh Compose test stack."""
import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration
if os.getenv("NEUROTRACE_INTEGRATION") != "1":
    pytest.skip("requires isolated Compose integration stack", allow_module_level=True)

from src.db import sessions
from src.main import app
from src.models.auth import User
from src.services import examinations as examinations_service
from src.services.auth import hash_password
from src.services.ml import MLClient
from src.services.preprocessing import PreprocessingClient

@pytest.fixture(autouse=True)
def clean_databases():
    with sessions.medical_engine.begin() as c: c.execute(text("TRUNCATE recent_examinations, recent_patients, examinations, patients CASCADE"))
    with sessions.auth_engine.begin() as c: c.execute(text("TRUNCATE refresh_tokens, users CASCADE"))
    with sessions.audit_engine.begin() as c: c.execute(text("TRUNCATE audit_logs CASCADE"))
    yield

@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(PreprocessingClient, "request", lambda self, examination_id, storage_bucket, storage_key, timestamps: None)
    monkeypatch.setattr(PreprocessingClient, "status", lambda self, examination_id: {"examination_id": str(examination_id), "status": "COMPLETED"})
    monkeypatch.setattr(MLClient, "results", lambda self, examination_id: {"examination_id": str(examination_id), "total_analyses_count": 1, "analyses": [{"analysis_id": 1, "time_stamp": 12.5, "result": 6.4, "confidence": 0.91}]})
    with sessions.AuthSession() as db:
        db.add_all([User(email="admin@integration.local", password_hash=hash_password("IntegrationPassword123!"), first_name="Admin", last_name="User", role="ADMIN", is_active=True), User(email="doctor@integration.local", password_hash=hash_password("IntegrationPassword123!"), first_name="Doctor", last_name="User", role="DOCTOR", is_active=True)]); db.commit()
    with TestClient(app) as client: yield client

def login(client, email="admin@integration.local", password="IntegrationPassword123!"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password}); assert response.status_code == 200; return response.json()
def h(tokens): return {"Authorization": f"Bearer {tokens['access_token']}"}

def test_all_current_business_endpoints(api):
    assert api.get("/health/live").status_code == 200; assert api.get("/health/ready").status_code == 200
    assert api.post("/api/v1/auth/login", json={"email":"admin@integration.local","password":"bad"}).status_code == 401
    tokens = login(api); headers = h(tokens)
    assert api.post("/api/v1/auth/refresh", json={"refresh_token":tokens["refresh_token"]}).status_code == 200
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert api.post("/api/v1/auth/change-password", headers=headers, json={"current_password":"IntegrationPassword123!","new_password":"ChangedPassword123!"}).status_code == 204
    headers = h(login(api, "admin@integration.local", "ChangedPassword123!"))
    assert api.patch("/api/v1/users/me", headers=headers, json={"first_name":"Changed"}).status_code == 200
    created = api.post("/api/v1/users", headers=headers, json={"email":"new@integration.local","password":"CreatedPassword123!","first_name":"New","last_name":"User","role":"DOCTOR"}); assert created.status_code == 201; user_id=created.json()["id"]
    assert api.get("/api/v1/users", headers=headers).status_code == 200; assert api.get(f"/api/v1/users/{user_id}", headers=headers).status_code == 200; assert api.patch(f"/api/v1/users/{user_id}", headers=headers, json={"last_name":"Updated","is_active":False}).status_code == 200; assert api.patch(f"/api/v1/users/{user_id}", headers=headers, json={"is_active":True}).status_code == 200
    with sessions.AuditSession() as audit:
        activated_event = audit.execute(text("SELECT 1 FROM audit_logs logs JOIN audit_log_types types ON types.id = logs.type_id WHERE types.code = 'ACCOUNT_ACTIVATED' AND logs.resource_id = :user_id"), {"user_id": user_id}).scalar()
        assert activated_event == 1
    assert api.get("/api/v1/users", headers=h(login(api,"doctor@integration.local"))).status_code == 403
    patient=api.post("/api/v1/patients",headers=headers); assert patient.status_code==201; patient_id=patient.json()["id"]
    for path in ("/api/v1/patients", "/api/v1/patients/stats", f"/api/v1/patients/{patient_id}", f"/api/v1/patients/{patient_id}/stats"): assert api.get(path,headers=headers).status_code==200
    upload=api.post("/api/v1/examinations",headers=headers,data={"patient_id":patient_id,"timestamps":"[\"00:00:00:000\"]"},files={"file":("integration.eeg",b"eeg","application/octet-stream")}); assert upload.status_code==201,upload.text; examination_id=upload.json()["id"]; assert upload.json()["status"] == "PREPROCESSING"
    assert api.get(f"/api/v1/examinations/{examination_id}", headers=headers).json()["analyses"] == []
    assert api.get(f"/api/v1/examinations/{examination_id}/results", headers=headers).status_code == 409
    with sessions.MedicalSession() as medical:
        assert examinations_service.mark_examination_ready(medical, examination_id)
    detail = api.get(f"/api/v1/examinations/{examination_id}", headers=headers).json(); assert detail["status"] == "READY"; assert detail["total_analyses_count"] == 1; assert detail["analyses"] == [{"analysis_id": 1, "time_stamp": 12.5, "result": 6.4, "confidence": 0.91}]
    for path in ("/api/v1/examinations",f"/api/v1/examinations/{examination_id}",f"/api/v1/patients/{patient_id}/examinations",f"/api/v1/examinations/{examination_id}/preprocessing-status",f"/api/v1/examinations/{examination_id}/results"): assert api.get(path,headers=headers).status_code==200
    assert api.patch(f"/api/v1/examinations/{examination_id}",headers=headers,json={"examination_date":"2026-11-05T12:00:00Z"}).status_code==200
    assert api.post("/api/v1/examinations/bulk-export",headers=headers,json={"examination_ids":[examination_id]}).status_code==200
    logs=api.get("/api/v1/admin/audit-logs",headers=headers); assert logs.status_code==200; assert api.get(f"/api/v1/admin/audit-logs/{logs.json()['items'][0]['id']}",headers=headers).status_code==200; activity=api.get("/api/v1/admin/app-activity",headers=headers); assert activity.status_code==200; assert {"active_users_last_24h","failed_login_attempts_last_24h","examinations_uploaded_last_24h","storage"} <= activity.json().keys()
    assert api.post("/api/v1/examinations/bulk-delete",headers=headers,json={"examination_ids":[examination_id]}).status_code==200; assert api.delete(f"/api/v1/examinations/{examination_id}",headers=headers).status_code==404
    assert api.post("/api/v1/auth/logout",headers=headers,json={"refresh_token":tokens["refresh_token"]}).status_code==204


def test_doctor_recent_resources_are_unique_ordered_and_capped(api):
    admin_headers = h(login(api))
    doctor_headers = h(login(api, "doctor@integration.local"))
    patient_ids = [api.post("/api/v1/patients", headers=admin_headers).json()["id"] for _ in range(11)]

    # Viewing a patient alone must not create recent history.
    assert api.get(f"/api/v1/patients/{patient_ids[0]}", headers=doctor_headers).status_code == 200
    assert api.get("/api/v1/me/recent/patients", headers=doctor_headers).json() == []

    patient_examination_ids = []
    for index, patient_id in enumerate(patient_ids):
        upload = api.post(
            "/api/v1/examinations",
            headers=admin_headers,
            data={"patient_id": patient_id, "timestamps": "[\"00:00:00:000\"]"},
            files={"file": (f"patient-{index}.eeg", b"eeg", "application/octet-stream")},
        )
        assert upload.status_code == 201, upload.text
        patient_examination_ids.append(upload.json()["id"])

    for examination_id in patient_examination_ids:
        assert api.get(f"/api/v1/examinations/{examination_id}", headers=doctor_headers).status_code == 200
    recent_patients = api.get("/api/v1/me/recent/patients", headers=doctor_headers)
    assert recent_patients.status_code == 200
    assert [item["id"] for item in recent_patients.json()] == list(reversed(patient_ids[1:]))
    assert all(item["last_visited_at"] for item in recent_patients.json())
    assert all(item["id"] == item["patient_id"] for item in recent_patients.json())
    assert all(item["examination_count"] == 1 for item in recent_patients.json())
    assert all(item["first_examination_date"] == item["last_examination_date"] for item in recent_patients.json())

    assert api.get(f"/api/v1/examinations/{patient_examination_ids[0]}", headers=doctor_headers).status_code == 200
    recent_patients = api.get("/api/v1/me/recent/patients", headers=doctor_headers)
    assert [item["id"] for item in recent_patients.json()] == [patient_ids[0], *reversed(patient_ids[2:])]
    assert api.get("/api/v1/me/recent/patients", headers=admin_headers).status_code == 403

    examination_ids = []
    for index in range(11):
        upload = api.post(
            "/api/v1/examinations",
            headers=admin_headers,
            data={"patient_id": patient_ids[0], "timestamps": "[\"00:00:00:000\"]"},
            files={"file": (f"recent-{index}.eeg", b"eeg", "application/octet-stream")},
        )
        assert upload.status_code == 201, upload.text
        examination_ids.append(upload.json()["id"])
    for examination_id in examination_ids:
        assert api.get(f"/api/v1/examinations/{examination_id}", headers=doctor_headers).status_code == 200
    recent_examinations = api.get("/api/v1/me/recent/examinations", headers=doctor_headers)
    assert recent_examinations.status_code == 200
    assert [item["id"] for item in recent_examinations.json()] == list(reversed(examination_ids[1:]))

    assert api.get(f"/api/v1/examinations/{examination_ids[0]}", headers=doctor_headers).status_code == 200
    recent_examinations = api.get("/api/v1/me/recent/examinations", headers=doctor_headers)
    assert [item["id"] for item in recent_examinations.json()] == [examination_ids[0], *reversed(examination_ids[2:])]