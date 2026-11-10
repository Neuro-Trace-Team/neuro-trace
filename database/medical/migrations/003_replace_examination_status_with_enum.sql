BEGIN;

DO $$
BEGIN
    CREATE TYPE examination_status AS ENUM ('PREPROCESSING', 'FINISHED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE examinations
    DROP CONSTRAINT IF EXISTS chk_examinations_status;

ALTER TABLE examinations
    ALTER COLUMN status DROP DEFAULT,
    ALTER COLUMN status TYPE examination_status
        USING (
            CASE status::text
                WHEN 'READY' THEN 'FINISHED'
                WHEN 'FINISHED' THEN 'FINISHED'
                ELSE 'PREPROCESSING'
            END
        )::examination_status,
    ALTER COLUMN status SET DEFAULT 'PREPROCESSING'::examination_status;

COMMIT;
