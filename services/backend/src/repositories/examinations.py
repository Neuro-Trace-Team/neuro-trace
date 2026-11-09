from datetime import datetime
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from src.models.medical import Examination, ExaminationEvent, ExaminationStatus


def get_examination(session: Session, examination_id: UUID, *, include_deleted: bool = False) -> Examination | None:
    statement = select(Examination).where(Examination.id == examination_id)
    if not include_deleted:
        statement = statement.where(Examination.deleted_at.is_(None))
    return session.scalar(statement)


def list_examinations(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None,
    examination_id: UUID | None,
    patient_id: UUID | None,
    uploaded_by: UUID | None,
    status: ExaminationStatus | None,
    examination_date_from: datetime | None,
    examination_date_to: datetime | None,
    sort_by: str,
    sort_order: str,
) -> tuple[list[Examination], int]:
    filters = [Examination.deleted_at.is_(None)]
    if query is not None:
        pattern = f"%{query}%"
        filters.append(or_(cast(Examination.id, String).ilike(pattern), cast(Examination.patient_id, String).ilike(pattern)))
    if examination_id is not None: filters.append(Examination.id == examination_id)
    if patient_id is not None: filters.append(Examination.patient_id == patient_id)
    if uploaded_by is not None: filters.append(Examination.uploaded_by == uploaded_by)
    if status is not None: filters.append(Examination.status == status)
    if examination_date_from is not None: filters.append(Examination.examination_date >= examination_date_from)
    if examination_date_to is not None: filters.append(Examination.examination_date <= examination_date_to)
    column = {
        "id": Examination.id,
        "patient_id": Examination.patient_id,
        "uploaded_by": Examination.uploaded_by,
        "status": Examination.status,
        "examination_date": Examination.examination_date,
        "created_at": Examination.created_at,
        "updated_at": Examination.updated_at,
    }[sort_by]
    order = column.asc() if sort_order == "asc" else column.desc()
    total = session.scalar(select(func.count()).select_from(Examination).where(*filters)) or 0
    rows = list(session.scalars(select(Examination).where(*filters).order_by(order, Examination.id.asc()).offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def list_events(session: Session, examination_id: UUID) -> list[ExaminationEvent]:
    return list(session.scalars(select(ExaminationEvent).where(ExaminationEvent.examination_id == examination_id).order_by(ExaminationEvent.timestamp, ExaminationEvent.created_at)))


def get_event(session: Session, examination_id: UUID, event_id: UUID) -> ExaminationEvent | None:
    return session.scalar(select(ExaminationEvent).where(ExaminationEvent.examination_id == examination_id, ExaminationEvent.id == event_id))
