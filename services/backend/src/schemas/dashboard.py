from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RecentExaminationResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_at: datetime
    processing_status: str


class DoctorDashboardResponse(BaseModel):
    total_patients: int
    total_examinations: int
    examinations_by_status: dict[str, int]
    total_analyses: int
    completed_analyses: int
    failed_analyses: int
    recent_examinations: list[RecentExaminationResponse]


class AdminDashboardResponse(BaseModel):
    period: str
    total_users: int
    active_users: int
    successful_logins: int
    failed_logins: int
    examinations_created: int
    analyses_created: int
    preprocessing_failures: int
    analysis_failures: int
    exports: int


class ActiveUsersStatisticsResponse(BaseModel):
    period: str
    active_users: int


class LoginAttemptsStatisticsResponse(BaseModel):
    period: str
    successful_logins: int
    failed_logins: int


class ExaminationsStatisticsResponse(BaseModel):
    period: str
    examinations_created: int


class ExportsStatisticsResponse(BaseModel):
    period: str
    exports: int
