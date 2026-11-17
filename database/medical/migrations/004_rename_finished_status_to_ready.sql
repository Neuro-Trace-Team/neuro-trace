BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumtypid = 'examination_status'::regtype
          AND enumlabel = 'FINISHED'
    ) THEN
        ALTER TYPE examination_status RENAME VALUE 'FINISHED' TO 'READY';
    END IF;
END $$;

COMMIT;
