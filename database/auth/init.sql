BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_users_role
        CHECK (role IN ('ADMIN', 'DOCTOR')),
    CONSTRAINT chk_users_email_not_blank
        CHECK (btrim(email) <> ''),
    CONSTRAINT chk_users_first_name_not_blank
        CHECK (btrim(first_name) <> ''),
    CONSTRAINT chk_users_last_name_not_blank
        CHECK (btrim(last_name) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_lower
    ON users (lower(email));

CREATE INDEX IF NOT EXISTS ix_users_role
    ON users (role);

CREATE INDEX IF NOT EXISTS ix_users_is_active
    ON users (is_active);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    last_used_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_refresh_tokens_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_refresh_tokens_token_hash
        UNIQUE (token_hash),
    CONSTRAINT chk_refresh_tokens_expiry
        CHECK (expires_at > created_at),
    CONSTRAINT chk_refresh_tokens_revoked_after_create
        CHECK (revoked_at IS NULL OR revoked_at >= created_at),
    CONSTRAINT chk_refresh_tokens_last_used_after_create
        CHECK (last_used_at IS NULL OR last_used_at >= created_at)
);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id
    ON refresh_tokens (user_id);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at
    ON refresh_tokens (expires_at);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_active
    ON refresh_tokens (user_id, expires_at)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_password_reset_tokens_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_password_reset_tokens_token_hash
        UNIQUE (token_hash),
    CONSTRAINT chk_password_reset_tokens_expiry
        CHECK (expires_at > created_at),
    CONSTRAINT chk_password_reset_tokens_used_after_create
        CHECK (used_at IS NULL OR used_at >= created_at)
);

CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id
    ON password_reset_tokens (user_id);

CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_expires_at
    ON password_reset_tokens (expires_at);

COMMIT;
