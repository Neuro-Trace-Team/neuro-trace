BEGIN;

INSERT INTO audit_log_types (code, name, description) VALUES
    ('ACCOUNT_CREATED', 'Utworzenie konta', 'Utworzenie konta użytkownika.'),
    ('LOGIN', 'Logowanie', 'Udane uwierzytelnienie użytkownika.'),
    ('FAILED_LOGIN_ATTEMPT', 'Nieudana próba logowania', 'Nieudana próba uwierzytelnienia użytkownika.'),
    ('LOGOUT', 'Wylogowanie', 'Zakończenie sesji przez użytkownika.'),
    ('PASSWORD_CHANGED', 'Zmiana hasła', 'Zmiana hasła przez zalogowanego użytkownika.'),
    ('PASSWORD_RESET', 'Reset hasła', 'Ustawienie nowego hasła w procedurze odzyskiwania dostępu.'),
    ('ROLE_CHANGED', 'Zmiana roli', 'Zmiana roli lub uprawnień użytkownika.'),
    ('ACCOUNT_DEACTIVATED', 'Dezaktywacja konta', 'Wyłączenie konta użytkownika.'),
    ('PATIENT_CREATED', 'Utworzenie pacjenta', 'Utworzenie rekordu pacjenta.'),
    ('PATIENT_ACCESSED', 'Dostęp do danych pacjenta', 'Odczyt danych pacjenta zgodnie z polityką audytową.'),
    ('STUDY_UPLOADED', 'Przesłanie badania', 'Dodanie pliku EEG do systemu.'),
    ('STUDY_UPDATED', 'Aktualizacja badania', 'Zmiana dozwolonych metadanych badania.'),
    ('STUDY_DELETED', 'Usunięcie badania', 'Logiczne usunięcie badania.'),
    ('ANALYSIS_REQUESTED', 'Zlecenie analizy', 'Zlecenie wykonania analizy AI/ML.'),
    ('ANALYSIS_COMPLETED', 'Zakończenie analizy', 'Analiza AI/ML została zakończona poprawnie.'),
    ('ANALYSIS_FAILED', 'Błąd analizy', 'Analiza AI/ML zakończyła się błędem.'),
    ('DATA_EXPORTED', 'Eksport danych', 'Wyeksportowanie danych z systemu.'),
    ('ACCESS_DENIED', 'Odmowa dostępu', 'Próba wykonania operacji bez wymaganych uprawnień.')
ON CONFLICT (code) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

COMMIT;
