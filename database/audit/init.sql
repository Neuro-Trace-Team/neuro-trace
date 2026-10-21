CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE audit_log_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID, -- Odniesienie logiczne do users(id) w auth_db
    type_id INTEGER REFERENCES audit_log_types(id) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

-- SEED DATA: Audyt
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