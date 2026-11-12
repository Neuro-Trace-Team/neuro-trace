BEGIN;

-- Example results for the four development examinations with fixed IDs.
-- These values are synthetic and do not represent clinical predictions.
INSERT INTO analyses (examination_id, event_timestamp, result, confidence, total_analyses_count, is_valid, invalid_reason)
VALUES
    ('20000000-0000-4000-8000-000000000001', 10.0, 3.2, 0.84, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000001', 20.0, 4.1, 0.79, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000001', 30.0, 3.7, 0.87, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000002', 10.0, 6.3, 0.82, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000002', 20.0, 5.8, 0.89, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000002', 30.0, 6.7, 0.81, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000003', 10.0, 2.4, 0.91, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000003', 20.0, 3.1, 0.85, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000003', 30.0, 2.8, 0.88, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000004', 10.0, 7.1, 0.80, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000004', 20.0, 6.5, 0.83, 3, TRUE, NULL),
    ('20000000-0000-4000-8000-000000000004', 30.0, 7.4, 0.86, 3, TRUE, NULL)
ON CONFLICT (examination_id, event_timestamp) DO NOTHING;

COMMIT;
