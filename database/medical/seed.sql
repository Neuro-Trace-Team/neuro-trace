BEGIN;

-- Słownik podstawowych kanałów EEG systemu 10-20.
-- Lista może zostać rozszerzona zgodnie z rzeczywistymi plikami używanymi w projekcie.
INSERT INTO eeg_channels (code, description) VALUES
    ('Fp1', 'Left frontopolar'),
    ('Fp2', 'Right frontopolar'),
    ('F7',  'Left anterior temporal'),
    ('F3',  'Left frontal'),
    ('Fz',  'Midline frontal'),
    ('F4',  'Right frontal'),
    ('F8',  'Right anterior temporal'),
    ('T7',  'Left temporal'),
    ('C3',  'Left central'),
    ('Cz',  'Midline central'),
    ('C4',  'Right central'),
    ('T8',  'Right temporal'),
    ('P7',  'Left posterior temporal'),
    ('P3',  'Left parietal'),
    ('Pz',  'Midline parietal'),
    ('P4',  'Right parietal'),
    ('P8',  'Right posterior temporal'),
    ('O1',  'Left occipital'),
    ('Oz',  'Midline occipital'),
    ('O2',  'Right occipital')
ON CONFLICT (code) DO NOTHING;

-- Celowo nie seedujemy pacjentów, badań, wyników analiz ani ocen bólu.
-- Są to dane transakcyjne/medyczne i powinny być tworzone przez aplikację,
-- testy integracyjne albo osobny zestaw fixture'ów developerskich.

COMMIT;