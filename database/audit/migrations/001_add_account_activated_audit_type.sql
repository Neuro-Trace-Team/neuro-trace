BEGIN;

INSERT INTO audit_log_types (code, name, description)
VALUES ('ACCOUNT_ACTIVATED', 'Aktywacja konta', 'Włączenie konta użytkownika.')
ON CONFLICT (code) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

COMMIT;
