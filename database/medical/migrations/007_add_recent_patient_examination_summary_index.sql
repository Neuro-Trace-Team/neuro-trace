BEGIN;

CREATE INDEX IF NOT EXISTS ix_examinations_active_patient_examination_date
    ON examinations (patient_id, examination_date) WHERE deleted_at IS NULL;

COMMIT;
