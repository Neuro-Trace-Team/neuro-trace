BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE examination_status AS ENUM ('PREPROCESSING', 'READY');

CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS examinations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), patient_id UUID NOT NULL, uploaded_by UUID NOT NULL,
    original_filename VARCHAR(255) NOT NULL, file_format VARCHAR(20) NOT NULL, file_size_bytes BIGINT NOT NULL,
    storage_bucket VARCHAR(100) NOT NULL, storage_key VARCHAR(1024) NOT NULL, file_checksum VARCHAR(64) NULL,
    status examination_status NOT NULL DEFAULT 'PREPROCESSING',
    examination_date TIMESTAMPTZ NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT fk_examinations_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT uq_examinations_storage_object UNIQUE (storage_bucket, storage_key),
    CONSTRAINT chk_examinations_filename_not_blank CHECK (btrim(original_filename) <> ''),
    CONSTRAINT chk_examinations_file_format_not_blank CHECK (btrim(file_format) <> ''),
    CONSTRAINT chk_examinations_file_size_positive CHECK (file_size_bytes > 0),
    CONSTRAINT chk_examinations_file_checksum_sha256 CHECK (file_checksum IS NULL OR file_checksum ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT chk_examinations_deleted_after_create CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE INDEX IF NOT EXISTS ix_examinations_patient_id ON examinations (patient_id);
CREATE INDEX IF NOT EXISTS ix_examinations_uploaded_by ON examinations (uploaded_by);
CREATE INDEX IF NOT EXISTS ix_examinations_created_at ON examinations (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_examinations_examination_date ON examinations (examination_date DESC);
CREATE INDEX IF NOT EXISTS ix_examinations_active ON examinations (patient_id, created_at DESC) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS examination_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), examination_id UUID NOT NULL,
    timestamp NUMERIC(12,6) NOT NULL, type VARCHAR(50) NOT NULL, description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_examination_events_examination FOREIGN KEY (examination_id) REFERENCES examinations(id) ON DELETE CASCADE,
    CONSTRAINT chk_examination_events_timestamp_nonnegative CHECK (timestamp >= 0),
    CONSTRAINT chk_examination_events_type_not_blank CHECK (btrim(type) <> '')
);

CREATE INDEX IF NOT EXISTS ix_examination_events_examination_timestamp ON examination_events (examination_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_examination_events_type ON examination_events (type);

-- `doctor_id` deliberately has no foreign key: users live in the separate
-- auth_db. Composite primary keys prevent duplicate history entries.
CREATE TABLE IF NOT EXISTS recent_patients (
    doctor_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (doctor_id, patient_id),
    CONSTRAINT fk_recent_patients_patient
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_recent_patients_doctor_visited
    ON recent_patients (doctor_id, visited_at DESC, patient_id);

CREATE TABLE IF NOT EXISTS recent_examinations (
    doctor_id UUID NOT NULL,
    examination_id UUID NOT NULL,
    visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (doctor_id, examination_id),
    CONSTRAINT fk_recent_examinations_examination
        FOREIGN KEY (examination_id) REFERENCES examinations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_recent_examinations_doctor_visited
    ON recent_examinations (doctor_id, visited_at DESC, examination_id);
COMMIT;
