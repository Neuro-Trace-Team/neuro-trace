from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, require_roles
from src.core.roles import Role
from src.db.sessions import get_audit_db, get_auth_db, get_medical_db
from src.models.audit import AuditLog, AuditLogType
from src.models.auth import User
from src.models.medical import Analysis, Examination, Patient, PreprocessingJob
from src.schemas.dashboard import (
    ActiveUsersStatisticsResponse,
    AdminDashboardResponse,
    DoctorDashboardResponse,
    ExaminationsStatisticsResponse,
    ExportsStatisticsResponse,
    LoginAttemptsStatisticsResponse,
    RecentExaminationResponse,
)

router = APIRouter(tags=["dashboard"])
admin_router = APIRouter(prefix="/admin", tags=["admin dashboard"])
admin_only = Depends(require_roles(Role.ADMIN))


def _period_start(period: str) -> datetime:
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period)
    if days is None:
        raise HTTPException(status_code=422, detail="period must be one of: 7d, 30d, 90d")
    return datetime.now(UTC) - timedelta(days=days)


def _audit_count(session: Session, code: str, since: datetime) -> int:
    return session.scalar(
        select(func.count()).select_from(AuditLog).join(AuditLogType).where(AuditLogType.code == code, AuditLog.created_at >= since)
    ) or 0


@router.get("/dashboard/stats", response_model=DoctorDashboardResponse)
def doctor_dashboard(
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> DoctorDashboardResponse:
    total_patients = medical_db.scalar(select(func.count()).select_from(Patient)) or 0
    total_examinations = medical_db.scalar(select(func.count()).select_from(Examination).where(Examination.deleted_at.is_(None))) or 0
    recent = list(medical_db.scalars(select(Examination).where(Examination.deleted_at.is_(None)).order_by(Examination.created_at.desc()).limit(10)))
    return DoctorDashboardResponse(total_patients=total_patients, total_examinations=total_examinations, recent_examinations=[RecentExaminationResponse(id=item.id, patient_id=item.patient_id, created_at=item.created_at, processing_status=item.processing_status) for item in recent])


def _admin_dashboard(period: str, auth_db: Session, medical_db: Session, audit_db: Session) -> AdminDashboardResponse:
    since = _period_start(period)
    return AdminDashboardResponse(
        period=period,
        total_users=auth_db.scalar(select(func.count()).select_from(User)) or 0,
        active_users=auth_db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0,
        successful_logins=_audit_count(audit_db, "LOGIN", since),
        failed_logins=_audit_count(audit_db, "FAILED_LOGIN_ATTEMPT", since),
        examinations_created=medical_db.scalar(select(func.count()).select_from(Examination).where(Examination.created_at >= since, Examination.deleted_at.is_(None))) or 0,
        analyses_created=medical_db.scalar(select(func.count()).select_from(Analysis).where(Analysis.created_at >= since)) or 0,
        preprocessing_failures=medical_db.scalar(select(func.count()).select_from(PreprocessingJob).where(PreprocessingJob.status == "FAILED", PreprocessingJob.completed_at >= since)) or 0,
        analysis_failures=medical_db.scalar(select(func.count()).select_from(Analysis).where(Analysis.status == "FAILED", Analysis.completed_at >= since)) or 0,
        exports=_audit_count(audit_db, "DATA_EXPORTED", since),
    )


@admin_router.get("/dashboard", response_model=AdminDashboardResponse, dependencies=[admin_only])
def admin_dashboard(period: str = Query(default="7d"), auth_db: Annotated[Session, Depends(get_auth_db)] = None, medical_db: Annotated[Session, Depends(get_medical_db)] = None, audit_db: Annotated[Session, Depends(get_audit_db)] = None) -> AdminDashboardResponse:
    return _admin_dashboard(period, auth_db, medical_db, audit_db)


@admin_router.get("/stats/active-users", response_model=ActiveUsersStatisticsResponse, dependencies=[admin_only])
def active_users_statistics(period: str = Query(default="7d"), auth_db: Annotated[Session, Depends(get_auth_db)] = None) -> ActiveUsersStatisticsResponse:
    _period_start(period)
    return ActiveUsersStatisticsResponse(period=period, active_users=auth_db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0)


@admin_router.get("/stats/login-attempts", response_model=LoginAttemptsStatisticsResponse, dependencies=[admin_only])
def login_attempts_statistics(period: str = Query(default="7d"), audit_db: Annotated[Session, Depends(get_audit_db)] = None) -> LoginAttemptsStatisticsResponse:
    since = _period_start(period)
    return LoginAttemptsStatisticsResponse(period=period, successful_logins=_audit_count(audit_db, "LOGIN", since), failed_logins=_audit_count(audit_db, "FAILED_LOGIN_ATTEMPT", since))


@admin_router.get("/stats/examinations", response_model=ExaminationsStatisticsResponse, dependencies=[admin_only])
def examinations_statistics(period: str = Query(default="30d"), medical_db: Annotated[Session, Depends(get_medical_db)] = None) -> ExaminationsStatisticsResponse:
    since = _period_start(period)
    return ExaminationsStatisticsResponse(period=period, examinations_created=medical_db.scalar(select(func.count()).select_from(Examination).where(Examination.created_at >= since, Examination.deleted_at.is_(None))) or 0)


@admin_router.get("/stats/exports", response_model=ExportsStatisticsResponse, dependencies=[admin_only])
def exports_statistics(period: str = Query(default="30d"), audit_db: Annotated[Session, Depends(get_audit_db)] = None) -> ExportsStatisticsResponse:
    return ExportsStatisticsResponse(period=period, exports=_audit_count(audit_db, "DATA_EXPORTED", _period_start(period)))
