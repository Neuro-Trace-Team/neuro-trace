BEGIN;

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    examination_id          UUID                NOT NULL,
    event_timestamp         DOUBLE PRECISION    NOT NULL,
    result                  DOUBLE PRECISION            ,
    confidence              DOUBLE PRECISION            ,
    total_analyses_count    INTEGER             NOT NULL,
    is_valid                BOOLEAN             NOT NULL,
    invalid_reason          TEXT                        ,

    CONSTRAINT ck_analyses_event_timestamp_non_negative
        CHECK (event_timestamp >= 0),
    CONSTRAINT ck_analyses_confidence_range
        CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_analyses_result_range
        CHECK (result BETWEEN 0 AND 10),
    CONSTRAINT ck_analyses_total_count_positive
        CHECK (total_analyses_count >= 1),
    CONSTRAINT ck_analyses_validity_shape CHECK (
        (is_valid AND result IS NOT NULL AND invalid_reason IS NULL)
        OR
        (NOT is_valid AND result IS NULL AND confidence IS NULL AND invalid_reason IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_analyses_examination_time
    ON analyses (examination_id, event_timestamp);

COMMIT;