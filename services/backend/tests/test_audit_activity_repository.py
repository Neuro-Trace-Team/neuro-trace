from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from src.repositories import audit


def test_app_activity_counts_use_existing_audit_events_since_the_period_start() -> None:
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        ("FAILED_LOGIN_ATTEMPT", 2),
        ("EXAMINATION_UPLOADED", 3),
        ("LOGIN", 5),
    ]
    session.scalar.return_value = 4
    since = datetime.now(UTC) - timedelta(hours=24)

    assert audit.app_activity_counts(session, since=since) == (4, 2, 3)

    statement = session.execute.call_args.args[0]
    compiled_statement = statement.compile(dialect=postgresql.dialect())
    compiled = str(compiled_statement)
    assert {"LOGIN", "FAILED_LOGIN_ATTEMPT", "EXAMINATION_UPLOADED"} <= set(compiled_statement.params["code_1"])
    assert "created_at >=" in compiled
