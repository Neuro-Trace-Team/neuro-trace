-- =============================================================================
-- SEED DATA: Wstępne dane testowe dla aplikacji NeuroTrace
-- =============================================================================

-- 1. Użytkownicy systemowi (Administrator oraz Lekarz)
-- Hasła dla obu użytkowników to: "password123" (wstępnie zahashowane bcrypt)
INSERT INTO users (id, email, password_hash, first_name, last_name, role, is_active) VALUES
('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'admin@neurotrace.local', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'Jan', 'Administrator', 'ADMIN', TRUE),
('b1eebc99-9c0b-4ef8-bb6d-6bb9bd380b22', 'doctor@neurotrace.local', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'Anna', 'Kowalska', 'DOCTOR', TRUE)
ON CONFLICT (email) DO NOTHING;

-- 2. Przykładowi pacjenci
INSERT INTO patients (id) VALUES
('c2eebc99-9c0b-4ef8-bb6d-6bb9bd380c33'),
('c3eebc99-9c0b-4ef8-bb6d-6bb9bd380c44')
ON CONFLICT (id) DO NOTHING;

-- 3. Kanały EEG (Standardowy zestaw elektrod systemu 10-20)[cite: 11]
INSERT INTO eeg_channels (code, description) VALUES
('Fp1', 'Frontopolar left'),
('Fp2', 'Frontopolar right'),
('F3', 'Frontal left'),
('F4', 'Frontal right'),
('C3', 'Central left'),
('C4', 'Central right'),
('P3', 'Parietal left'),
('P4', 'Parietal right'),
('O1', 'Occipital left'),
('O2', 'Occipital right'),
('Fz', 'Frontal midline'),
('Cz', 'Central midline'),
('Pz', 'Parietal midline')
ON CONFLICT (code) DO NOTHING;

-- 4. Przykładowe badanie EEG przypisane do pierwszego pacjenta i lekarza[cite: 11]
INSERT INTO studies (
    id, 
    patient_id, 
    uploaded_by, 
    original_filename, 
    study_date, 
    sampling_frequency, 
    electrode_positions, 
    reference, 
    power_line_frequency, 
    storage_key
) VALUES (
    'd4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55',
    'c2eebc99-9c0b-4ef8-bb6d-6bb9bd380c33',
    'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380b22',
    'eeg_patient_sample_01.edf',
    NOW() - INTERVAL '2 days',
    256,
    '{"system": "10-20", "total_electrodes": 7}'::jsonb,
    'Cz',
    50,
    'studies/c2eebc99-9c0b-4ef8-bb6d-6bb9bd380c33/d4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55.edf'
)
ON CONFLICT (id) DO NOTHING;

-- 5. Powiązanie badania z konkretnymi kanałami EEG (tabela asocjacyjna)[cite: 11]
INSERT INTO study_channels (study_id, channel_id, position) 
SELECT 
    'd4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55'::UUID, 
    id, 
    row_number() OVER (ORDER BY id) as position
FROM eeg_channels
WHERE code IN ('Fp1', 'Fp2', 'F3', 'F4', 'C3', 'C4', 'Cz')
ON CONFLICT (study_id, channel_id) DO NOTHING;

-- 6. Zdarzenia zarejestrowane podczas badania (np. bodźce lub adnotacje)[cite: 11]
INSERT INTO study_events (id, study_id, timestamp, type, description, metadata_json) VALUES
('e5eebc99-9c0b-4ef8-bb6d-6bb9bd380e66', 'd4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55', 12.500000, 'STIMULUS', 'Pojawienie się bodźca świetlnego', '{"stimulus_type": "flash", "duration_ms": 500}'::jsonb),
('e6eebc99-9c0b-4ef8-bb6d-6bb9bd380e67', 'd4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55', 45.200000, 'ANNOTATION', 'Wystąpienie artefaktów ruchowych pacjenta', '{"severity": "moderate"}'::jsonb)
ON CONFLICT (id) DO NOTHING;