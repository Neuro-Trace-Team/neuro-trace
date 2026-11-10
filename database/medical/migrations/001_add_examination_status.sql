BEGIN;

ALTER TABLE examinations
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'PROCESSING';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_examinations_status'
    ) THEN
        ALTER TABLE examinations
            ADD CONSTRAINT chk_examinations_status
            CHECK (status IN ('PROCESSING', 'READY'));
    END IF;
END $$;

COMMIT;
