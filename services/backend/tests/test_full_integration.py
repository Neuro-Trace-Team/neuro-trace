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
    with sessions.medical_engine.begin() as c: c.execute(text("TRUNCATE examination_events, examinations, patients CASCADE"))
    with sessions.auth_engine.begin() as c: c.execute(text("TRUNCATE password_reset_tokens, refresh_tokens, users CASCADE"))
    with sessions.audit_engine.begin() as c: c.execute(text("TRUNCATE audit_logs CASCADE"))
    yield

@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(PreprocessingClient, "request", lambda self, examination_id, storage_bucket, storage_key: None)
    monkeypatch.setattr(PreprocessingClient, "status", lambda self, examination_id: {"examination_id": str(examination_id), "status": "COMPLETED"})
    monkeypatch.setattr(MLClient, "results", lambda self, examination_id: {"examination_id": str(examination_id), "total_analyses_count": 1, "analyses": [{"analysis_id": 1, "time_stamp": 1.0, "result": 6.4, "confidence": 0.91}]})
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
    assert api.post("/api/v1/auth/forgot-password", json={"email":"admin@integration.local"}).status_code == 202
    assert api.post("/api/v1/auth/reset-password", json={"token":"bad","new_password":"ReplacementPassword123!"}).status_code == 400
    assert api.post("/api/v1/auth/change-password", headers=headers, json={"current_password":"IntegrationPassword123!","new_password":"ChangedPassword123!"}).status_code == 204
    headers = h(login(api, "admin@integration.local", "ChangedPassword123!"))
    assert api.patch("/api/v1/users/me", headers=headers, json={"first_name":"Changed"}).status_code == 200
    created = api.post("/api/v1/users", headers=headers, json={"email":"new@integration.local","password":"CreatedPassword123!","first_name":"New","last_name":"User","role":"DOCTOR"}); assert created.status_code == 201; user_id=created.json()["id"]
    assert api.get("/api/v1/users", headers=headers).status_code == 200; assert api.get(f"/api/v1/users/{user_id}", headers=headers).status_code == 200; assert api.patch(f"/api/v1/users/{user_id}", headers=headers, json={"last_name":"Updated","is_active":False}).status_code == 200
    assert api.get("/api/v1/users", headers=h(login(api,"doctor@integration.local"))).status_code == 403
    patient=api.post("/api/v1/patients",headers=headers); assert patient.status_code==201; patient_id=patient.json()["id"]
    for path in ("/api/v1/patients", "/api/v1/patients/stats", f"/api/v1/patients/{patient_id}", f"/api/v1/patients/{patient_id}/stats"): assert api.get(path,headers=headers).status_code==200
    upload=api.post("/api/v1/examinations",headers=headers,data={"patient_id":patient_id},files={"file":("integration.eeg",b"eeg","application/octet-stream")}); assert upload.status_code==201,upload.text; examination_id=upload.json()["id"]; assert upload.json()["status"] == "PROCESSING"
    assert api.get(f"/api/v1/examinations/{examination_id}/results", headers=headers).status_code == 409
    with sessions.MedicalSession() as medical:
        assert examinations_service.mark_examination_ready(medical, examination_id)
    assert api.get(f"/api/v1/examinations/{examination_id}", headers=headers).json()["status"] == "READY"
    for path in ("/api/v1/examinations",f"/api/v1/examinations/{examination_id}",f"/api/v1/patients/{patient_id}/examinations",f"/api/v1/examinations/{examination_id}/events",f"/api/v1/examinations/{examination_id}/preprocessing-status",f"/api/v1/examinations/{examination_id}/results"): assert api.get(path,headers=headers).status_code==200
    assert api.patch(f"/api/v1/examinations/{examination_id}",headers=headers,json={"examination_date":"2026-11-05T12:00:00Z"}).status_code==200
    event=api.post(f"/api/v1/examinations/{examination_id}/events",headers=headers,json={"timestamp":1,"type":"stimulus"}); assert event.status_code==201; event_id=event.json()["id"]
    assert api.patch(f"/api/v1/examinations/{examination_id}/events/{event_id}",headers=headers,json={"description":"updated"}).status_code==200; assert api.delete(f"/api/v1/examinations/{examination_id}/events/{event_id}",headers=headers).status_code==204
    assert api.post("/api/v1/examinations/bulk-export",headers=headers,json={"examination_ids":[examination_id]}).status_code==200
    logs=api.get("/api/v1/admin/audit-logs",headers=headers); assert logs.status_code==200; assert api.get(f"/api/v1/admin/audit-logs/{logs.json()['items'][0]['id']}",headers=headers).status_code==200
    assert api.post("/api/v1/examinations/bulk-delete",headers=headers,json={"examination_ids":[examination_id]}).status_code==200; assert api.delete(f"/api/v1/examinations/{examination_id}",headers=headers).status_code==404
    assert api.post("/api/v1/auth/logout",headers=headers,json={"refresh_token":tokens["refresh_token"]}).status_code==204
