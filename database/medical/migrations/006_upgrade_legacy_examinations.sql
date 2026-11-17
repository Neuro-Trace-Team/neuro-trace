BEGIN;

-- Preserve legacy metadata and statuses while making the current backend schema usable.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'examination_status') THEN
        CREATE TYPE examination_status AS ENUM ('PREPROCESSING', 'READY');
    ELSIF NOT EXISTS (
        SELECT 1 FROM pg_enum WHERE enumtypid = 'examination_status'::regtype AND enumlabel = 'READY'
    ) THEN
        RAISE EXCEPTION 'examination_status does not contain READY; apply migration 004 first';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'examinations' AND column_name = 'status'
    ) THEN
        ALTER TABLE examinations ADD COLUMN status examination_status;
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'examinations' AND column_name = 'processing_status'
        ) THEN
            UPDATE examinations SET status = CASE
                WHEN processing_status = 'READY' THEN 'READY'::examination_status
                ELSE 'PREPROCESSING'::examination_status
            END;
        ELSE
            UPDATE examinations SET status = 'PREPROCESSING'::examination_status;
        END IF;
        ALTER TABLE examinations ALTER COLUMN status SET DEFAULT 'PREPROCESSING'::examination_status;
        ALTER TABLE examinations ALTER COLUMN status SET NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'examinations' AND column_name = 'sampling_frequency'
    ) THEN
        ALTER TABLE examinations ALTER COLUMN sampling_frequency DROP NOT NULL;
    END IF;
END $$;

COMMIT;
