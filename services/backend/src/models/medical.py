from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import MedicalBase


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
    examination_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sampling_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    electrode_positions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reference: Mapped[str | None] = mapped_column(String(50))
    power_line_frequency: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="UPLOADED")


class EEGChannel(MedicalBase):
    __tablename__ = "eeg_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))


class ExaminationChannel(MedicalBase):
    __tablename__ = "examination_channels"
    __table_args__ = (UniqueConstraint("examination_id", "position"),)

    examination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("eeg_channels.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class ExaminationEvent(MedicalBase):
    __tablename__ = "examination_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    examination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PreprocessingJob(MedicalBase):
    __tablename__ = "preprocessing_jobs"
    __table_args__ = (
        UniqueConstraint("id", "examination_id"),
        UniqueConstraint("output_bucket", "output_storage_key"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    examination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("examinations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="QUEUED")
    pipeline_version: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_bucket: Mapped[str | None] = mapped_column(String(100))
    output_storage_key: Mapped[str | None] = mapped_column(String(1024))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Analysis(MedicalBase):
    __tablename__ = "analyses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["preprocessing_job_id", "examination_id"],
            ["preprocessing_jobs.id", "preprocessing_jobs.examination_id"],
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    examination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("examinations.id"), nullable=False)
    preprocessing_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    requested_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="QUEUED")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class AnalysisResult(MedicalBase):
    __tablename__ = "analysis_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    analysis_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True, nullable=False)
    pain_level: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    explanation_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PainAssessment(MedicalBase):
    __tablename__ = "pain_assessments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    examination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("examinations.id"), nullable=False)
    assessed_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    pain_level: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    scale: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
