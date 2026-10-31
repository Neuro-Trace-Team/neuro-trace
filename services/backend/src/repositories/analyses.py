from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.medical import Analysis, AnalysisResult


def get_analysis(session: Session, analysis_id: UUID) -> Analysis | None:
    return session.scalar(select(Analysis).where(Analysis.id == analysis_id))


def get_result(session: Session, analysis_id: UUID) -> AnalysisResult | None:
    return session.scalar(select(AnalysisResult).where(AnalysisResult.analysis_id == analysis_id))


def list_analyses(
    session: Session,
    *,
    page: int,
    page_size: int,
    examination_id: UUID | None = None,
    requested_by: UUID | None = None,
    status: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Analysis], int]:
    filters = []
    if examination_id is not None:
        filters.append(Analysis.examination_id == examination_id)
    if requested_by is not None:
        filters.append(Analysis.requested_by == requested_by)
    if status is not None:
        filters.append(Analysis.status == status)
    total = session.scalar(select(func.count()).select_from(Analysis).where(*filters)) or 0
    sort_columns = {
        "created_at": Analysis.created_at,
        "started_at": Analysis.started_at,
        "completed_at": Analysis.completed_at,
        "status": Analysis.status,
    }
    order_column = sort_columns[sort_by]
    ordering = order_column.asc() if sort_order == "asc" else order_column.desc()
    analyses = list(
        session.scalars(
            select(Analysis)
            .where(*filters)
            .order_by(ordering, Analysis.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return analyses, total


def list_results(
    session: Session, *, examination_id: UUID, page: int, page_size: int
) -> tuple[list[tuple[Analysis, AnalysisResult]], int]:
    filters = [Analysis.examination_id == examination_id, Analysis.status == "COMPLETED"]
    total = (
        session.scalar(
            select(func.count())
            .select_from(Analysis)
            .join(AnalysisResult, AnalysisResult.analysis_id == Analysis.id)
            .where(*filters)
        )
        or 0
    )
    rows = list(
        session.execute(
            select(Analysis, AnalysisResult)
            .join(AnalysisResult, AnalysisResult.analysis_id == Analysis.id)
            .where(*filters)
            .order_by(Analysis.completed_at.desc(), Analysis.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total
