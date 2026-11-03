from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.medical import PainAssessment
from src.repositories import pain_assessments as pain_assessments_repository
from src.services import examinations as examinations_service


def _now() -> datetime:
    return datetime.now(UTC)


def create_assessment(
    session: Session,
    *,
    examination_id: UUID,
    assessed_by: UUID,
    pain_level: Decimal,
    scale: str,
    notes: str | None,
    assessed_at: datetime | None,
) -> PainAssessment:
    examinations_service.get_examination(session, examination_id)
    assessment = PainAssessment(
        examination_id=examination_id,
        assessed_by=assessed_by,
        pain_level=pain_level,
        scale=scale.strip(),
        notes=notes,
        assessed_at=assessed_at or _now(),
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return assessment


def list_assessments(
    session: Session, *, examination_id: UUID, page: int, page_size: int
) -> tuple[list[PainAssessment], int]:
    examinations_service.get_examination(session, examination_id)
    return pain_assessments_repository.list_assessments(
        session, examination_id=examination_id, page=page, page_size=page_size
    )
