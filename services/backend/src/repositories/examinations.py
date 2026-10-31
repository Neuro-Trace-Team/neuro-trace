from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.medical import (
    EEGChannel,
    Examination,
    ExaminationChannel,
    ExaminationEvent,
    PainAssessment,
    Analysis,
    AnalysisResult,
)


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
    patient_id: UUID | None,
    uploaded_by: UUID | None,
    processing_status: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    channel: str | None = None,
    pain_level: Decimal | None = None,
    pain_level_min: Decimal | None = None,
    pain_level_max: Decimal | None = None,
    pain_source: str = "doctor",
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Examination], int]:
    filters = [Examination.deleted_at.is_(None)]
    if patient_id is not None:
        filters.append(Examination.patient_id == patient_id)
    if uploaded_by is not None:
        filters.append(Examination.uploaded_by == uploaded_by)
    if processing_status is not None:
        filters.append(Examination.processing_status == processing_status)
    if date_from is not None:
        filters.append(Examination.created_at >= date_from)
    if date_to is not None:
        filters.append(Examination.created_at <= date_to)
    if channel is not None:
        matching_examinations = (
            select(ExaminationChannel.examination_id)
            .join(EEGChannel, EEGChannel.id == ExaminationChannel.channel_id)
            .where(EEGChannel.code == channel)
        )
        filters.append(Examination.id.in_(matching_examinations))

    if pain_source == "ai":
        pain_value = (
            select(AnalysisResult.pain_level)
            .join(Analysis, Analysis.id == AnalysisResult.analysis_id)
            .where(Analysis.examination_id == Examination.id, Analysis.status == "COMPLETED")
            .order_by(AnalysisResult.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
    else:
        pain_value = (
            select(PainAssessment.pain_level)
            .where(PainAssessment.examination_id == Examination.id)
            .order_by(PainAssessment.assessed_at.desc(), PainAssessment.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
    if pain_level is not None:
        filters.append(pain_value == pain_level)
    if pain_level_min is not None:
        filters.append(pain_value >= pain_level_min)
    if pain_level_max is not None:
        filters.append(pain_value <= pain_level_max)
    sort_columns = {
        "created_at": Examination.created_at,
        "examination_date": Examination.examination_date,
        "processing_status": Examination.processing_status,
    }
    order_column = sort_columns[sort_by]
    ordering = order_column.asc() if sort_order == "asc" else order_column.desc()
    total = session.scalar(select(func.count()).select_from(Examination).where(*filters)) or 0
    rows = list(
        session.scalars(
            select(Examination)
            .where(*filters)
            .order_by(ordering, Examination.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def list_eeg_channels(session: Session) -> list[EEGChannel]:
    return list(session.scalars(select(EEGChannel).order_by(EEGChannel.code)))


def get_eeg_channels_by_ids(session: Session, channel_ids: set[int]) -> list[EEGChannel]:
    return list(session.scalars(select(EEGChannel).where(EEGChannel.id.in_(channel_ids))))


def list_examination_channels(session: Session, examination_id: UUID) -> list[tuple[ExaminationChannel, EEGChannel]]:
    return list(
        session.execute(
            select(ExaminationChannel, EEGChannel)
            .join(EEGChannel, EEGChannel.id == ExaminationChannel.channel_id)
            .where(ExaminationChannel.examination_id == examination_id)
            .order_by(ExaminationChannel.position)
        )
    )


def list_events(session: Session, examination_id: UUID) -> list[ExaminationEvent]:
    return list(
        session.scalars(
            select(ExaminationEvent)
            .where(ExaminationEvent.examination_id == examination_id)
            .order_by(ExaminationEvent.timestamp, ExaminationEvent.created_at)
        )
    )


def get_event(session: Session, *, examination_id: UUID, event_id: UUID) -> ExaminationEvent | None:
    return session.scalar(
        select(ExaminationEvent).where(
            ExaminationEvent.id == event_id, ExaminationEvent.examination_id == examination_id
        )
    )
