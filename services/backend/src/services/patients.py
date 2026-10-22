from uuid import UUID

from sqlalchemy.orm import Session

from src.models.medical import Examination, Patient
from src.repositories import patients as patients_repository


class PatientNotFoundError(Exception):
    pass


def create_patient(session: Session) -> Patient:
    patient = Patient()
    patients_repository.create_patient(session, patient)
    session.commit()
    session.refresh(patient)
    return patient


def get_patient(session: Session, patient_id: UUID) -> Patient:
    patient = patients_repository.get_patient(session, patient_id)
    if patient is None:
        raise PatientNotFoundError
    return patient


def list_patients(
    session: Session, *, page: int, page_size: int, search: str | None = None
) -> tuple[list[Patient], int]:
    return patients_repository.list_patients(session, page=page, page_size=page_size, search=search)


def patient_statistics(session: Session) -> tuple[int, int, int]:
    return patients_repository.patient_statistics(session)


def list_patient_examinations(
    session: Session, *, patient_id: UUID, page: int, page_size: int
) -> tuple[list[Examination], int]:
    get_patient(session, patient_id)
    return patients_repository.list_patient_examinations(
        session, patient_id=patient_id, page=page, page_size=page_size
    )
