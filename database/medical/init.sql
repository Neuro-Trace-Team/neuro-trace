CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE studies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id) ON DELETE CASCADE NOT NULL,
    uploaded_by UUID NOT NULL, -- Odniesienie logiczne do users(id) w auth_db
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

-- SEED DATA: Medyczne
INSERT INTO patients (id) VALUES
('c2eebc99-9c0b-4ef8-bb6d-6bb9bd380c33'),
('c3eebc99-9c0b-4ef8-bb6d-6bb9bd380c44')
ON CONFLICT (id) DO NOTHING;

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

INSERT INTO studies (
    id, patient_id, uploaded_by, original_filename, study_date, 
    sampling_frequency, electrode_positions, reference, power_line_frequency, storage_key
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

INSERT INTO study_channels (study_id, channel_id, position) 
SELECT 
    'd4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55'::UUID, 
    id, 
    row_number() OVER (ORDER BY id) as position
FROM eeg_channels
WHERE code IN ('Fp1', 'Fp2', 'F3', 'F4', 'C3', 'C4', 'Cz')
ON CONFLICT (study_id, channel_id) DO NOTHING;

INSERT INTO study_events (id, study_id, timestamp, type, description, metadata_json) VALUES
('e5eebc99-9c0b-4ef8-bb6d-6bb9bd380e66', 'd4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55', 12.500000, 'STIMULUS', 'Pojawienie się bodźca świetlnego', '{"stimulus_type": "flash", "duration_ms": 500}'::jsonb),
('e6eebc99-9c0b-4ef8-bb6d-6bb9bd380e67', 'd4eebc99-9c0b-4ef8-bb6d-6bb9bd380d55', 45.200000, 'ANNOTATION', 'Wystąpienie artefaktów ruchowych pacjenta', '{"severity": "moderate"}'::jsonb)
ON CONFLICT (id) DO NOTHING;