from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_medical_schema_has_only_current_domain_tables() -> None:
    schema = (ROOT / "database" / "medical" / "init.sql").read_text(encoding="utf-8")
    assert {"patients", "examinations", "recent_patients", "recent_examinations"} <= {
        line.split()[5] for line in schema.splitlines() if line.startswith("CREATE TABLE IF NOT EXISTS")
    }
    for obsolete in ("pain_assessments", "preprocessing_jobs", "analyses", "analysis_results", "eeg_channels", "examination_channels"):
        assert f"CREATE TABLE IF NOT EXISTS {obsolete}" not in schema


def test_medical_schema_excludes_transferred_data() -> None:
    schema = (ROOT / "database" / "medical" / "init.sql").read_text(encoding="utf-8")
    for obsolete in ("processing_status", "sampling_frequency", "electrode_positions", "reference", "power_line_frequency", "duration_seconds", "metadata_json"):
        assert obsolete not in schema
    for field in ("storage_bucket", "storage_key", "file_checksum", "status", "deleted_at"):
        assert field in schema
    assert "examination_events" not in schema


def test_recent_resource_history_schema_is_bounded_by_doctor_and_resource() -> None:
    schema = (ROOT / "database" / "medical" / "init.sql").read_text(encoding="utf-8")
    migration = (ROOT / "database" / "medical" / "migrations" / "002_add_recent_resources.sql").read_text(encoding="utf-8")
    for source in (schema, migration):
        assert "PRIMARY KEY (doctor_id, patient_id)" in source
        assert "PRIMARY KEY (doctor_id, examination_id)" in source
        assert "visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in source
        assert "ix_recent_patients_doctor_visited" in source
        assert "ix_recent_examinations_doctor_visited" in source


def test_recent_patient_summary_query_has_an_active_examination_index() -> None:
    schema = (ROOT / "database" / "medical" / "init.sql").read_text(encoding="utf-8")
    migration = (ROOT / "database" / "medical" / "migrations" / "007_add_recent_patient_examination_summary_index.sql").read_text(encoding="utf-8")
    for source in (schema, migration):
        assert "ix_examinations_active_patient_examination_date" in source
        assert "(patient_id, examination_date) WHERE deleted_at IS NULL" in source


def test_examination_status_is_a_database_enum_with_a_data_migration() -> None:
    schema = (ROOT / "database" / "medical" / "init.sql").read_text(encoding="utf-8")
    migration = (ROOT / "database" / "medical" / "migrations" / "003_replace_examination_status_with_enum.sql").read_text(encoding="utf-8")
    rename_migration = (ROOT / "database" / "medical" / "migrations" / "004_rename_finished_status_to_ready.sql").read_text(encoding="utf-8")
    assert "CREATE TYPE examination_status AS ENUM ('PREPROCESSING', 'READY')" in schema
    assert "status examination_status NOT NULL DEFAULT 'PREPROCESSING'" in schema
    assert "WHEN 'READY' THEN 'FINISHED'" in migration
    assert "ALTER TYPE examination_status RENAME VALUE 'FINISHED' TO 'READY'" in rename_migration
