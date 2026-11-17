BEGIN;

-- doctor_id is a UUID from auth_db, so it cannot have a cross-database FK.
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
