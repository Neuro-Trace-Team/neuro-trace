from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.medical import PainAssessment


def list_assessments(
    session: Session, *, examination_id: UUID, page: int, page_size: int
) -> tuple[list[PainAssessment], int]:
    filters = [PainAssessment.examination_id == examination_id]
    total = session.scalar(select(func.count()).select_from(PainAssessment).where(*filters)) or 0
    assessments = list(
        session.scalars(
            select(PainAssessment)
            .where(*filters)
            .order_by(PainAssessment.assessed_at.desc(), PainAssessment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return assessments, total
