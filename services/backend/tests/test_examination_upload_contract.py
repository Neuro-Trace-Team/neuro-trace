import pytest
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import UploadFile
from pydantic import ValidationError

from src.api.v1.examinations import parse_upload_events
from src.schemas.examinations import ExaminationEventCreate
from src.services import examinations as examination_service


def test_upload_events_accept_frontend_timestamp_format() -> None:
    events = parse_upload_events('[{"timestamp":"01:02:03:123456","type":"ARTIFACT"}]')
    assert events == [{"timestamp": Decimal("3723.123456"), "type": "ARTIFACT", "description": None}]


def test_upload_events_reject_invalid_json_before_upload() -> None:
    with pytest.raises(ValueError, match="JSON array"):
        parse_upload_events('{"timestamp":"00:00:01:000001"}')


def test_event_endpoint_accepts_frontend_timestamp_format() -> None:
    event = ExaminationEventCreate(timestamp="00:00:01:000001", type="ARTIFACT")
    assert event.timestamp == Decimal("1.000001")


def test_event_endpoint_rejects_malformed_timestamp() -> None:
    with pytest.raises(ValidationError, match="timestamp"):
        ExaminationEventCreate(timestamp="01:99:00:1", type="ARTIFACT")


@pytest.mark.asyncio
async def test_invalid_upload_does_not_create_generated_patient() -> None:
    session = MagicMock()
    file = UploadFile(filename="invalid.txt", file=BytesIO(b"not eeg"))
    with pytest.raises(examination_service.ExaminationValidationError, match="Unsupported EEG format"):
        await examination_service.upload_examination(
            session,
            patient_id=None,
            generate_patient=True,
            uploaded_by=uuid4(),
            file=file,
            examination_date=None,
            events=[],
        )
    session.add.assert_not_called()
