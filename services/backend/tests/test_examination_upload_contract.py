import pytest
from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import UploadFile

from src.services import examinations as examination_service


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
        )
    session.add.assert_not_called()


def test_timestamps_must_be_a_non_empty_json_array_in_the_frontend_format() -> None:
    assert examination_service.parse_timestamps('["00:00:00:000000", "23:59:59:123456"]') == [
        "00:00:00:000000", "23:59:59:123456"
    ]
    with pytest.raises(examination_service.ExaminationValidationError, match="HH:MM:SS:ffffff"):
        examination_service.parse_timestamps('["00:00:00.000"]')


def test_extracts_examination_date_from_edf_header() -> None:
    header = bytearray(256)
    header[168:176] = b"05.11.26"
    header[176:184] = b"14.30.45"

    assert examination_service._extract_recording_datetime(BytesIO(header), "edf").isoformat() == "2026-11-05T14:30:45+00:00"
