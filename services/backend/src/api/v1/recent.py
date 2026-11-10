from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.core.roles import Role
from src.db.sessions import get_medical_db
from src.models.auth import User
from src.schemas.recent import RecentExaminationResponse, RecentPatientResponse
from src.services import recent as recent_service

router = APIRouter(prefix="/me/recent", tags=["recent resources"])
doctor_only = require_roles(Role.DOCTOR)


@router.get("/patients", response_model=list[RecentPatientResponse])
def list_recent_patients(
    current_user: Annotated[User, Depends(doctor_only)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
) -> list[RecentPatientResponse]:
    return [
        RecentPatientResponse(
            id=patient.id,
            patient_id=patient.id,
            created_at=patient.created_at,
            updated_at=patient.updated_at,
            last_visited_at=visited_at,
            first_examination_date=first_examination_date,
            last_examination_date=last_examination_date,
            examination_count=examination_count,
        )
        for patient, visited_at, first_examination_date, last_examination_date, examination_count
        in recent_service.list_recent_patients(medical_db, doctor_id=current_user.id)
    ]


@router.get("/examinations", response_model=list[RecentExaminationResponse])
def list_recent_examinations(
    current_user: Annotated[User, Depends(doctor_only)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
) -> list[RecentExaminationResponse]:
    return [
        RecentExaminationResponse(
            id=examination.id,
            patient_id=examination.patient_id,
            uploaded_by=examination.uploaded_by,
            original_filename=examination.original_filename,
            file_format=examination.file_format,
            file_size_bytes=examination.file_size_bytes,
            file_checksum=examination.file_checksum,
            status=examination.status,
            examination_date=examination.examination_date,
            created_at=examination.created_at,
            updated_at=examination.updated_at,
            last_visited_at=visited_at,
        )
        for examination, visited_at in recent_service.list_recent_examinations(medical_db, doctor_id=current_user.id)
    ]
