CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE user_role AS ENUM ('ADMIN', 'DOCTOR');


CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_log_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    type_id INTEGER REFERENCES audit_log_types(id) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

CREATE TABLE studies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE NOT NULL,
    uploaded_by UUID REFERENCES users(id) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    study_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    sampling_frequency INTEGER NOT NULL,
    electrode_positions JSONB,
    reference VARCHAR(50),
    power_line_frequency INTEGER,
    storage_key VARCHAR(255)
);

CREATE TABLE eeg_channels (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255)
);

CREATE TABLE study_channels (
    study_id UUID REFERENCES studies(id) ON DELETE CASCADE,
    channel_id INTEGER REFERENCES eeg_channels(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (study_id, channel_id)
);

CREATE TABLE study_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID REFERENCES studies(id) ON DELETE CASCADE NOT NULL,
    timestamp NUMERIC(12, 6) NOT NULL,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO audit_log_types (code, name, description) VALUES
('ACCOUNT_CREATED', 'Utworzenie konta', 'Utworzenie konta użytkownika.'),
('LOGIN', 'Logowanie', 'Udane uwierzytelnienie użytkownika.'),
('FAILED_LOGIN_ATTEMPT', 'Nieudana próba logowania', 'Nieudana próba uwierzytelnienia.'),
('LOGOUT', 'Wylogowanie', 'Zakończenie sesji przez użytkownika.'),
('PASSWORD_CHANGED', 'Zmiana hasła', 'Zmiana hasła zalogowanego użytkownika.'),
('PASSWORD_RESET', 'Reset hasła', 'Ustawienie nowego hasła za pomocą procedury odzyskiwania dostępu.'),
('ROLE_CHANGED', 'Zmiana roli', 'Zmiana uprawnień użytkownika.'),
('ACCOUNT_DEACTIVATED', 'Dezaktywacja konta', 'Wyłączenie konta użytkownika.'),
('DATA_EXPORTED', 'Eksport danych', 'Wyeksportowanie danych z systemu.'),
('PATIENT_ACCESSED', 'Dostęp do danych pacjenta', 'Odczyt danych pacjenta.'),
('STUDY_UPLOADED', 'Przesłanie badania', 'Dodanie pliku EEG do systemu.'),
('STUDY_DELETED', 'Usunięcie badania', 'Usunięcie lub oznaczenie badania jako usuniętego.'),
('ACCESS_DENIED', 'Odmowa dostępu', 'Próba wykonania operacji bez wymaganych uprawnień.')
ON CONFLICT (code) DO NOTHING;