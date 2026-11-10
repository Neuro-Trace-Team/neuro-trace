from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_account_activated_is_available_in_fresh_and_existing_audit_databases() -> None:
    seed = (ROOT / "database" / "audit" / "seed.sql").read_text(encoding="utf-8")
    migration = (ROOT / "database" / "audit" / "migrations" / "001_add_account_activated_audit_type.sql").read_text(encoding="utf-8")

    assert "ACCOUNT_ACTIVATED" in seed
    assert "ACCOUNT_ACTIVATED" in migration
