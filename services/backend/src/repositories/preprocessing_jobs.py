from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.medical import PreprocessingJob


def get_job(session: Session, job_id: UUID) -> PreprocessingJob | None:
    return session.scalar(select(PreprocessingJob).where(PreprocessingJob.id == job_id))


def list_jobs(
    session: Session, *, examination_id: UUID, page: int, page_size: int
) -> tuple[list[PreprocessingJob], int]:
    filters = [PreprocessingJob.examination_id == examination_id]
    total = session.scalar(select(func.count()).select_from(PreprocessingJob).where(*filters)) or 0
    jobs = list(
        session.scalars(
            select(PreprocessingJob)
            .where(*filters)
            .order_by(PreprocessingJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return jobs, total
