from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import MedicalBase


class ExaminationStatus(str, Enum):
    PREPROCESSING = "PREPROCESSING"
    READY = "READY"


class Patient(MedicalBase):
    __tablename__ = "patients"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Examination(MedicalBase):
    __tablename__ = "examinations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_checksum: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[ExaminationStatus] = mapped_column(SQLEnum(ExaminationStatus, name="examination_status"), nullable=False, default=ExaminationStatus.PREPROCESSING, server_default=ExaminationStatus.PREPROCESSING.value)
    examination_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExaminationEvent(MedicalBase):
    __tablename__ = "examination_events"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    examination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RecentPatient(MedicalBase):
    __tablename__ = "recent_patients"

    doctor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RecentExamination(MedicalBase):
    __tablename__ = "recent_examinations"

    doctor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    examination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), primary_key=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
