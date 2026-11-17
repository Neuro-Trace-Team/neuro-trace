BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS audit_log_types (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(100) NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT NULL,

    CONSTRAINT uq_audit_log_types_code UNIQUE (code),
    CONSTRAINT chk_audit_log_types_code_not_blank CHECK (btrim(code) <> ''),
    CONSTRAINT chk_audit_log_types_name_not_blank CHECK (btrim(name) <> '')
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NULL,
    type_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB NULL,
    ip_address INET NULL,
    request_id UUID NULL,
    resource_type VARCHAR(50) NULL,
    resource_id UUID NULL,

    CONSTRAINT fk_audit_logs_type
        FOREIGN KEY (type_id)
        REFERENCES audit_log_types(id),
    CONSTRAINT chk_audit_logs_resource_type_not_blank
        CHECK (resource_type IS NULL OR btrim(resource_type) <> '')
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at
    ON audit_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_user_created_at
    ON audit_logs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_type_created_at
    ON audit_logs (type_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id
    ON audit_logs (request_id)
    WHERE request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_audit_logs_resource
    ON audit_logs (resource_type, resource_id)
    WHERE resource_type IS NOT NULL AND resource_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_audit_logs_metadata_gin
    ON audit_logs USING GIN (metadata_json)
    WHERE metadata_json IS NOT NULL;

COMMIT;
