from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_medical_schema_has_only_current_domain_tables() -> None:
    schema = (ROOT / "database" / "medical" / "init.sql").read_text(encoding="utf-8")
    assert {"patients", "examinations", "examination_events"} <= {
        line.split()[5] for line in schema.splitlines() if line.startswith("CREATE TABLE IF NOT EXISTS")
    }
    for obsolete in ("pain_assessments", "preprocessing_jobs", "analyses", "analysis_results", "eeg_channels", "examination_channels"):
        assert f"CREATE TABLE IF NOT EXISTS {obsolete}" not in schema


def test_examination_and_event_schema_exclude_transferred_data() -> None:
    schema = (ROOT / "database" / "medical" / "init.sql").read_text(encoding="utf-8")
    for obsolete in ("processing_status", "sampling_frequency", "electrode_positions", "reference", "power_line_frequency", "duration_seconds", "metadata_json"):
        assert obsolete not in schema
    for field in ("storage_bucket", "storage_key", "file_checksum", "deleted_at", "timestamp", "description"):
        assert field in schema
