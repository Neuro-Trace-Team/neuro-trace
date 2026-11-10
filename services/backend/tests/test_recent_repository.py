from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from src.models.medical import RecentExamination, RecentPatient
from src.repositories import recent


def _compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_record_recent_patient_upserts_and_trims_under_a_doctor_lock() -> None:
    session = MagicMock()

    recent.record_recent_patient(session, doctor_id=uuid4(), patient_id=uuid4())

    statements = [call.args[0] for call in session.execute.call_args_list]
    assert "pg_advisory_xact_lock" in str(statements[0])
    assert "ON CONFLICT (doctor_id, patient_id) DO UPDATE" in _compiled(statements[1])
    assert "OFFSET %(param_1)s" in _compiled(statements[2])
    session.commit.assert_called_once()


def test_record_recent_examination_uses_the_examination_composite_key() -> None:
    session = MagicMock()

    recent.record_recent_examination(session, doctor_id=uuid4(), examination_id=uuid4())

    statement = session.execute.call_args_list[1].args[0]
    assert "ON CONFLICT (doctor_id, examination_id) DO UPDATE" in _compiled(statement)
    assert RecentPatient.__tablename__ == "recent_patients"
    assert RecentExamination.__tablename__ == "recent_examinations"
