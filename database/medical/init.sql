BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS studies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL,
    uploaded_by UUID NOT NULL,

    original_filename VARCHAR(255) NOT NULL,
    file_format VARCHAR(20) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    storage_bucket VARCHAR(100) NOT NULL,
    storage_key VARCHAR(1024) NOT NULL,
    file_checksum VARCHAR(64) NULL,

    study_date TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,

    sampling_frequency INTEGER NOT NULL,
    electrode_positions JSONB NULL,
    reference VARCHAR(50) NULL,
    power_line_frequency INTEGER NULL,
    duration_seconds NUMERIC(12,6) NULL,
    processing_status VARCHAR(30) NOT NULL DEFAULT 'UPLOADED',

    CONSTRAINT fk_studies_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(id),
    CONSTRAINT uq_studies_storage_object
        UNIQUE (storage_bucket, storage_key),
    CONSTRAINT chk_studies_filename_not_blank
        CHECK (btrim(original_filename) <> ''),
    CONSTRAINT chk_studies_file_format_not_blank
        CHECK (btrim(file_format) <> ''),
    CONSTRAINT chk_studies_file_size_positive
        CHECK (file_size_bytes > 0),
    CONSTRAINT chk_studies_sampling_frequency_positive
        CHECK (sampling_frequency > 0),
    CONSTRAINT chk_studies_power_line_frequency
        CHECK (power_line_frequency IS NULL OR power_line_frequency IN (50, 60)),
    CONSTRAINT chk_studies_duration_positive
        CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    CONSTRAINT chk_studies_file_checksum_sha256
        CHECK (file_checksum IS NULL OR file_checksum ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT chk_studies_processing_status
        CHECK (processing_status IN (
            'UPLOADING',
            'UPLOADED',
            'VALIDATING',
            'VALIDATED',
            'PREPROCESSING',
            'READY',
            'FAILED'
        )),
    CONSTRAINT chk_studies_deleted_after_create
        CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE INDEX IF NOT EXISTS ix_studies_patient_id
    ON studies (patient_id);

CREATE INDEX IF NOT EXISTS ix_studies_uploaded_by
    ON studies (uploaded_by);

CREATE INDEX IF NOT EXISTS ix_studies_created_at
    ON studies (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_studies_study_date
    ON studies (study_date DESC);

CREATE INDEX IF NOT EXISTS ix_studies_processing_status
    ON studies (processing_status);

CREATE INDEX IF NOT EXISTS ix_studies_active
    ON studies (patient_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS eeg_channels (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(50) NOT NULL,
    description VARCHAR(255) NULL,

    CONSTRAINT uq_eeg_channels_code UNIQUE (code),
    CONSTRAINT chk_eeg_channels_code_not_blank CHECK (btrim(code) <> '')
);

CREATE TABLE IF NOT EXISTS study_channels (
    study_id UUID NOT NULL,
    channel_id INTEGER NOT NULL,
    position INTEGER NOT NULL,

    CONSTRAINT pk_study_channels PRIMARY KEY (study_id, channel_id),
    CONSTRAINT fk_study_channels_study
        FOREIGN KEY (study_id)
        REFERENCES studies(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_study_channels_channel
        FOREIGN KEY (channel_id)
        REFERENCES eeg_channels(id),
    CONSTRAINT uq_study_channels_position
        UNIQUE (study_id, position),
    CONSTRAINT chk_study_channels_position_nonnegative
        CHECK (position >= 0)
);

CREATE INDEX IF NOT EXISTS ix_study_channels_channel_id
    ON study_channels (channel_id);

CREATE TABLE IF NOT EXISTS study_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL,
    timestamp NUMERIC(12,6) NOT NULL,
    type VARCHAR(50) NOT NULL,
    description TEXT NULL,
    metadata_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_study_events_study
        FOREIGN KEY (study_id)
        REFERENCES studies(id)
        ON DELETE CASCADE,
    CONSTRAINT chk_study_events_timestamp_nonnegative
        CHECK (timestamp >= 0),
    CONSTRAINT chk_study_events_type_not_blank
        CHECK (btrim(type) <> '')
);

CREATE INDEX IF NOT EXISTS ix_study_events_study_timestamp
    ON study_events (study_id, timestamp);

CREATE INDEX IF NOT EXISTS ix_study_events_type
    ON study_events (type);

CREATE TABLE IF NOT EXISTS preprocessing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    pipeline_version VARCHAR(100) NOT NULL,
    parameters_json JSONB NULL,
    output_bucket VARCHAR(100) NULL,
    output_storage_key VARCHAR(1024) NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_preprocessing_jobs_study
        FOREIGN KEY (study_id)
        REFERENCES studies(id),
    CONSTRAINT uq_preprocessing_jobs_id_study
        UNIQUE (id, study_id),
    CONSTRAINT uq_preprocessing_output_object
        UNIQUE (output_bucket, output_storage_key),
    CONSTRAINT chk_preprocessing_jobs_status
        CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    CONSTRAINT chk_preprocessing_jobs_pipeline_version_not_blank
        CHECK (btrim(pipeline_version) <> ''),
    CONSTRAINT chk_preprocessing_jobs_started_after_create
        CHECK (started_at IS NULL OR started_at >= created_at),
    CONSTRAINT chk_preprocessing_jobs_completed_after_create
        CHECK (completed_at IS NULL OR completed_at >= created_at),
    CONSTRAINT chk_preprocessing_jobs_completed_after_started
        CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at),
    CONSTRAINT chk_preprocessing_output_pair
        CHECK (
            (output_bucket IS NULL AND output_storage_key IS NULL)
            OR
            (output_bucket IS NOT NULL AND output_storage_key IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS ix_preprocessing_jobs_study_id
    ON preprocessing_jobs (study_id);

CREATE INDEX IF NOT EXISTS ix_preprocessing_jobs_status
    ON preprocessing_jobs (status);

CREATE INDEX IF NOT EXISTS ix_preprocessing_jobs_created_at
    ON preprocessing_jobs (created_at DESC);

CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL,
    preprocessing_job_id UUID NOT NULL,
    requested_by UUID NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error_message TEXT NULL,

    CONSTRAINT fk_analyses_study
        FOREIGN KEY (study_id)
        REFERENCES studies(id),
    CONSTRAINT fk_analyses_preprocessing_job_same_study
        FOREIGN KEY (preprocessing_job_id, study_id)
        REFERENCES preprocessing_jobs(id, study_id),
    CONSTRAINT chk_analyses_status
        CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    CONSTRAINT chk_analyses_model_name_not_blank
        CHECK (btrim(model_name) <> ''),
    CONSTRAINT chk_analyses_model_version_not_blank
        CHECK (btrim(model_version) <> ''),
    CONSTRAINT chk_analyses_started_after_create
        CHECK (started_at IS NULL OR started_at >= created_at),
    CONSTRAINT chk_analyses_completed_after_create
        CHECK (completed_at IS NULL OR completed_at >= created_at),
    CONSTRAINT chk_analyses_completed_after_started
        CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
);

CREATE INDEX IF NOT EXISTS ix_analyses_study_id
    ON analyses (study_id);

CREATE INDEX IF NOT EXISTS ix_analyses_preprocessing_job_id
    ON analyses (preprocessing_job_id);

CREATE INDEX IF NOT EXISTS ix_analyses_requested_by
    ON analyses (requested_by);

CREATE INDEX IF NOT EXISTS ix_analyses_status
    ON analyses (status);

CREATE INDEX IF NOT EXISTS ix_analyses_created_at
    ON analyses (created_at DESC);

CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL,
    pain_level NUMERIC(5,2) NULL,
    confidence NUMERIC(5,4) NULL,
    result_json JSONB NULL,
    explanation_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_analysis_results_analysis
        FOREIGN KEY (analysis_id)
        REFERENCES analyses(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_analysis_results_analysis
        UNIQUE (analysis_id),
    CONSTRAINT chk_analysis_results_confidence
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE IF NOT EXISTS pain_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL,
    assessed_by UUID NOT NULL,
    pain_level NUMERIC(5,2) NOT NULL,
    scale VARCHAR(50) NOT NULL,
    notes TEXT NULL,
    assessed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_pain_assessments_study
        FOREIGN KEY (study_id)
        REFERENCES studies(id),
    CONSTRAINT chk_pain_assessments_level_nonnegative
        CHECK (pain_level >= 0),
    CONSTRAINT chk_pain_assessments_scale_not_blank
        CHECK (btrim(scale) <> '')
);

CREATE INDEX IF NOT EXISTS ix_pain_assessments_study_id
    ON pain_assessments (study_id);

CREATE INDEX IF NOT EXISTS ix_pain_assessments_assessed_by
    ON pain_assessments (assessed_by);

CREATE INDEX IF NOT EXISTS ix_pain_assessments_assessed_at
    ON pain_assessments (assessed_at DESC);

COMMIT;
