"""Business operations for a doctor's recently visited resources."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.medical import Examination, Patient
from src.repositories import recent as repository


def record_patient_visit(session: Session, *, doctor_id: UUID, patient_id: UUID) -> None:
    repository.record_recent_patient(session, doctor_id=doctor_id, patient_id=patient_id)


def record_examination_visit(session: Session, *, doctor_id: UUID, examination_id: UUID) -> None:
    repository.record_recent_examination(session, doctor_id=doctor_id, examination_id=examination_id)


def list_recent_patients(
    session: Session, *, doctor_id: UUID
) -> list[tuple[Patient, datetime, datetime | None, datetime | None, int]]:
    return repository.list_recent_patients(session, doctor_id=doctor_id)


def list_recent_examinations(session: Session, *, doctor_id: UUID) -> list[tuple[Examination, datetime]]:
    return repository.list_recent_examinations(session, doctor_id=doctor_id)
