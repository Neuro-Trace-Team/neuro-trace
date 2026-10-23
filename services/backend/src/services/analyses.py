from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.medical import Analysis, AnalysisResult
from src.repositories import analyses as analyses_repository
from src.services import examinations as examinations_service
from src.services import preprocessing_jobs as preprocessing_jobs_service


class AnalysisNotFoundError(Exception):
    pass


class AnalysisResultNotFoundError(Exception):
    pass


class AnalysisValidationError(Exception):
    pass


class AnalysisTransitionError(Exception):
    pass


_ACTIVE_STATUSES = frozenset({"QUEUED", "RUNNING"})


def _now() -> datetime:
    return datetime.now(UTC)


def _get_analysis(session: Session, analysis_id: UUID) -> Analysis:
    analysis = analyses_repository.get_analysis(session, analysis_id)
    if analysis is None:
        raise AnalysisNotFoundError
    return analysis


def _commit(session: Session, record: Analysis | AnalysisResult) -> Analysis | AnalysisResult:
    session.commit()
    session.refresh(record)
    return record


def _require_status(analysis: Analysis, allowed: frozenset[str]) -> None:
    if analysis.status not in allowed:
        raise AnalysisTransitionError(f"Cannot transition analysis from {analysis.status}")


def create_analysis(
    session: Session,
    *,
    examination_id: UUID,
    preprocessing_job_id: UUID,
    requested_by: UUID,
    model_name: str,
    model_version: str,
) -> Analysis:
    examinations_service.get_examination(session, examination_id)
    preprocessing_job = preprocessing_jobs_service.get_preprocessing_job(session, preprocessing_job_id)
    if preprocessing_job.examination_id != examination_id:
        raise AnalysisValidationError("Preprocessing job does not belong to this examination")
    if preprocessing_job.status != "COMPLETED":
        raise AnalysisValidationError("Analysis requires a completed preprocessing job")
    model_name = model_name.strip()
    model_version = model_version.strip()
    if not model_name or not model_version:
        raise AnalysisValidationError("Model name and version must not be blank")
    analysis = Analysis(
        examination_id=examination_id,
        preprocessing_job_id=preprocessing_job_id,
        requested_by=requested_by,
        status="QUEUED",
        model_name=model_name,
        model_version=model_version,
    )
    session.add(analysis)
    return _commit(session, analysis)


def get_analysis(session: Session, analysis_id: UUID) -> Analysis:
    return _get_analysis(session, analysis_id)


def list_analyses(
    session: Session,
    *,
    page: int,
    page_size: int,
    examination_id: UUID | None = None,
    requested_by: UUID | None = None,
    status: str | None = None,
) -> tuple[list[Analysis], int]:
    if examination_id is not None:
        examinations_service.get_examination(session, examination_id)
    return analyses_repository.list_analyses(
        session,
        page=page,
        page_size=page_size,
        examination_id=examination_id,
        requested_by=requested_by,
        status=status,
    )


def mark_running(session: Session, analysis_id: UUID) -> Analysis:
    analysis = _get_analysis(session, analysis_id)
    _require_status(analysis, frozenset({"QUEUED"}))
    analysis.status = "RUNNING"
    analysis.started_at = _now()
    return _commit(session, analysis)


def mark_completed(
    session: Session,
    *,
    analysis_id: UUID,
    pain_level: Decimal | None,
    confidence: Decimal | None,
    result: dict[str, Any] | None,
    explanation: dict[str, Any] | None,
) -> tuple[Analysis, AnalysisResult]:
    analysis = _get_analysis(session, analysis_id)
    _require_status(analysis, _ACTIVE_STATUSES)
    if analyses_repository.get_result(session, analysis_id) is not None:
        raise AnalysisTransitionError("Analysis already has a result")
    now = _now()
    analysis.status = "COMPLETED"
    analysis.started_at = analysis.started_at or now
    analysis.completed_at = now
    analysis.error_message = None
    result_record = AnalysisResult(
        analysis_id=analysis.id,
        pain_level=pain_level,
        confidence=confidence,
        result_json=result,
        explanation_json=explanation,
    )
    session.add(result_record)
    session.commit()
    session.refresh(analysis)
    session.refresh(result_record)
    return analysis, result_record


def mark_failed(session: Session, *, analysis_id: UUID, error_message: str) -> Analysis:
    analysis = _get_analysis(session, analysis_id)
    _require_status(analysis, _ACTIVE_STATUSES)
    analysis.status = "FAILED"
    analysis.completed_at = _now()
    analysis.error_message = error_message.strip()
    return _commit(session, analysis)


def mark_cancelled(session: Session, analysis_id: UUID) -> Analysis:
    analysis = _get_analysis(session, analysis_id)
    _require_status(analysis, _ACTIVE_STATUSES)
    analysis.status = "CANCELLED"
    analysis.completed_at = _now()
    return _commit(session, analysis)


def get_analysis_result(session: Session, analysis_id: UUID) -> AnalysisResult:
    _get_analysis(session, analysis_id)
    result = analyses_repository.get_result(session, analysis_id)
    if result is None:
        raise AnalysisResultNotFoundError
    return result


def list_examination_results(
    session: Session, *, examination_id: UUID, page: int, page_size: int
) -> tuple[list[tuple[Analysis, AnalysisResult]], int]:
    examinations_service.get_examination(session, examination_id)
    return analyses_repository.list_results(
        session, examination_id=examination_id, page=page, page_size=page_size
    )
