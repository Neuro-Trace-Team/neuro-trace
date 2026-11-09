"""Persistence operations for per-doctor recently visited resources."""

from datetime import datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.models.medical import Examination, Patient, RecentExamination, RecentPatient

MAX_RECENT_RESOURCES = 10
RecentModel = TypeVar("RecentModel", RecentPatient, RecentExamination)


def _lock_doctor_history(session: Session, doctor_id: UUID, resource_type: str) -> None:
    """Serialize trim/upsert pairs for one doctor's one resource history."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key)::bigint)"),
        {"lock_key": f"recent:{resource_type}:{doctor_id}"},
    )


def _upsert_and_trim(
    session: Session,
    *,
    model: type[RecentModel],
    resource_column: object,
    doctor_id: UUID,
    resource_id: UUID,
    resource_type: str,
) -> None:
    _lock_doctor_history(session, doctor_id, resource_type)
    session.execute(
        insert(model)
        .values(doctor_id=doctor_id, visited_at=func.clock_timestamp(), **{resource_column.key: resource_id})
        .on_conflict_do_update(
            index_elements=(model.doctor_id, resource_column),
            set_={"visited_at": func.clock_timestamp()},
        )
    )
    overflow = (
        select(resource_column)
        .where(model.doctor_id == doctor_id)
        .order_by(model.visited_at.desc(), resource_column.asc())
        .offset(MAX_RECENT_RESOURCES)
        .subquery()
    )
    session.execute(
        delete(model).where(
            model.doctor_id == doctor_id,
            resource_column.in_(select(overflow.c[resource_column.key])),
        )
    )
    session.commit()


def record_recent_patient(session: Session, *, doctor_id: UUID, patient_id: UUID) -> None:
    _upsert_and_trim(
        session,
        model=RecentPatient,
        resource_column=RecentPatient.patient_id,
        doctor_id=doctor_id,
        resource_id=patient_id,
        resource_type="patients",
    )


def record_recent_examination(session: Session, *, doctor_id: UUID, examination_id: UUID) -> None:
    _upsert_and_trim(
        session,
        model=RecentExamination,
        resource_column=RecentExamination.examination_id,
        doctor_id=doctor_id,
        resource_id=examination_id,
        resource_type="examinations",
    )


def list_recent_patients(session: Session, *, doctor_id: UUID) -> list[tuple[Patient, datetime]]:
    return list(
        session.execute(
            select(Patient, RecentPatient.visited_at)
            .join(RecentPatient, RecentPatient.patient_id == Patient.id)
            .where(RecentPatient.doctor_id == doctor_id)
            .order_by(RecentPatient.visited_at.desc(), Patient.id.asc())
            .limit(MAX_RECENT_RESOURCES)
        ).all()
    )


def list_recent_examinations(session: Session, *, doctor_id: UUID) -> list[tuple[Examination, datetime]]:
    return list(
        session.execute(
            select(Examination, RecentExamination.visited_at)
            .join(RecentExamination, RecentExamination.examination_id == Examination.id)
            .where(RecentExamination.doctor_id == doctor_id, Examination.deleted_at.is_(None))
            .order_by(RecentExamination.visited_at.desc(), Examination.id.asc())
            .limit(MAX_RECENT_RESOURCES)
        ).all()
    )
