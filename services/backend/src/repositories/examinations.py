from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.medical import Examination, ExaminationEvent


def get_examination(session: Session, examination_id: UUID, *, include_deleted: bool = False) -> Examination | None:
    statement = select(Examination).where(Examination.id == examination_id)
    if not include_deleted:
        statement = statement.where(Examination.deleted_at.is_(None))
    return session.scalar(statement)


def list_examinations(session: Session, *, page: int, page_size: int, patient_id: UUID | None, uploaded_by: UUID | None, date_from: datetime | None, date_to: datetime | None, sort_by: str, sort_order: str) -> tuple[list[Examination], int]:
    filters = [Examination.deleted_at.is_(None)]
    if patient_id is not None: filters.append(Examination.patient_id == patient_id)
    if uploaded_by is not None: filters.append(Examination.uploaded_by == uploaded_by)
    if date_from is not None: filters.append(Examination.created_at >= date_from)
    if date_to is not None: filters.append(Examination.created_at <= date_to)
    column = {"created_at": Examination.created_at, "examination_date": Examination.examination_date}[sort_by]
    order = column.asc() if sort_order == "asc" else column.desc()
    total = session.scalar(select(func.count()).select_from(Examination).where(*filters)) or 0
    rows = list(session.scalars(select(Examination).where(*filters).order_by(order, Examination.id.asc()).offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def list_events(session: Session, examination_id: UUID) -> list[ExaminationEvent]:
    return list(session.scalars(select(ExaminationEvent).where(ExaminationEvent.examination_id == examination_id).order_by(ExaminationEvent.timestamp, ExaminationEvent.created_at)))


def get_event(session: Session, examination_id: UUID, event_id: UUID) -> ExaminationEvent | None:
    return session.scalar(select(ExaminationEvent).where(ExaminationEvent.examination_id == examination_id, ExaminationEvent.id == event_id))
