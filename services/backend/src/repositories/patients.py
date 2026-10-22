from uuid import UUID

from sqlalchemy import String, cast, distinct, func, select
from sqlalchemy.orm import Session

from src.models.medical import Examination, Patient


def create_patient(session: Session, patient: Patient) -> Patient:
    session.add(patient)
    return patient


def get_patient(session: Session, patient_id: UUID) -> Patient | None:
    return session.get(Patient, patient_id)


def list_patients(
    session: Session, *, page: int, page_size: int, search: str | None = None
) -> tuple[list[Patient], int]:
    filters = []
    if search:
        filters.append(cast(Patient.id, String).ilike(f"%{search.strip()}%"))
    total = session.scalar(select(func.count()).select_from(Patient).where(*filters)) or 0
    patients = list(
        session.scalars(
            select(Patient)
            .where(*filters)
            .order_by(Patient.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return patients, total


def patient_statistics(session: Session) -> tuple[int, int, int]:
    total_patients = session.scalar(select(func.count()).select_from(Patient)) or 0
    patients_with_examinations = session.scalar(
        select(func.count(distinct(Examination.patient_id))).where(Examination.deleted_at.is_(None))
    ) or 0
    active_examinations = session.scalar(
        select(func.count()).select_from(Examination).where(Examination.deleted_at.is_(None))
    ) or 0
    return total_patients, patients_with_examinations, active_examinations


def list_patient_examinations(
    session: Session, *, patient_id: UUID, page: int, page_size: int
) -> tuple[list[Examination], int]:
    filters = (Examination.patient_id == patient_id, Examination.deleted_at.is_(None))
    total = session.scalar(select(func.count()).select_from(Examination).where(*filters)) or 0
    examinations = list(
        session.scalars(
            select(Examination)
            .where(*filters)
            .order_by(Examination.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return examinations, total
