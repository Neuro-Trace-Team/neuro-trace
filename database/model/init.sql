BEGIN;

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    examination_id       UUID             NOT NULL,
    event_timestamp           DOUBLE PRECISION NOT NULL,
    result               DOUBLE PRECISION NOT NULL,
    confidence           DOUBLE PRECISION NOT NULL,
    total_analyses_count INTEGER          NOT NULL,

    CONSTRAINT ck_analyses_event_timestamp_non_negative
        CHECK (event_timestamp >= 0),
    CONSTRAINT ck_analyses_confidence_range
        CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_analyses_total_count_positive
        CHECK (total_analyses_count >= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_analyses_examination_time
    ON analyses (examination_id, event_timestamp);

COMMIT;