from datetime import datetime
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
    session: Session, *, page: int, page_size: int, search: str | None = None,
    created_from: datetime | None = None, created_to: datetime | None = None,
    sort_by: str = "created_at", sort_order: str = "desc",
) -> tuple[list[Patient], int]:
    filters = []
    if search:
        filters.append(cast(Patient.id, String).ilike(f"%{search.strip()}%"))
    if created_from is not None:
        filters.append(Patient.created_at >= created_from)
    if created_to is not None:
        filters.append(Patient.created_at <= created_to)
    sort_columns = {"created_at": Patient.created_at, "updated_at": Patient.updated_at}
    order_column = sort_columns[sort_by]
    ordering = order_column.asc() if sort_order == "asc" else order_column.desc()
    total = session.scalar(select(func.count()).select_from(Patient).where(*filters)) or 0
    patients = list(
        session.scalars(
            select(Patient)
            .where(*filters)
            .order_by(ordering, Patient.id.asc())
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


def patient_examination_statistics(session: Session, patient_id: UUID) -> tuple[int, datetime | None, datetime | None]:
    filters = (Examination.patient_id == patient_id, Examination.deleted_at.is_(None))
    row = session.execute(
        select(
            func.count(Examination.id),
            func.min(Examination.created_at),
            func.max(Examination.created_at),
        ).where(*filters)
    ).one()
    return row[0], row[1], row[2]


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
