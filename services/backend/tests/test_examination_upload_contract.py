import pytest
from io import BytesIO
from types import SimpleNamespace
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
            timestamps=[],
        )
    session.add.assert_not_called()


def test_timestamps_convert_frontend_format_to_milliseconds_and_allow_empty_array() -> None:
    assert examination_service.parse_timestamps('["00:00:00:000", "99:59:59:123"]') == [
        0, 359999123
    ]
    assert examination_service.parse_timestamps('[]') == []


def test_milliseconds_convert_back_to_frontend_timestamp_format() -> None:
    assert examination_service.milliseconds_to_timestamp(83456) == "00:01:23:456"
    assert examination_service.milliseconds_to_timestamp(359999123) == "99:59:59:123"


@pytest.mark.parametrize("value", ['["00:00:00.000"]', '["00:00:00:000000"]', '["00:60:00:000"]', '[12]', '{}'])
def test_timestamps_reject_invalid_values(value: str) -> None:
    with pytest.raises(examination_service.ExaminationValidationError):
        examination_service.parse_timestamps(value)


def test_extracts_examination_date_from_edf_header() -> None:
    header = bytearray(256)
    header[168:176] = b"05.11.26"
    header[176:184] = b"14.30.45"

    assert examination_service._extract_recording_datetime(BytesIO(header), "edf").isoformat() == "2026-11-05T14:30:45+00:00"


@pytest.mark.asyncio
async def test_upload_stores_timestamp_json_next_to_recording(monkeypatch) -> None:
    patient_id = uuid4()
    examination_id = uuid4()
    storage = MagicMock()
    uploads: dict[str, tuple[bytes, str | None]] = {}

    def upload(source, *, key, content_type):
        uploads[key] = (source.read(), content_type)

    storage.upload.side_effect = upload
    monkeypatch.setattr(examination_service, "RustFSStorage", lambda: storage)
    monkeypatch.setattr(examination_service, "get_settings", lambda: SimpleNamespace(max_upload_size_bytes=1024, rustfs_bucket="examinations"))
    monkeypatch.setattr(examination_service.patients_service, "get_patient", lambda *_: object())
    monkeypatch.setattr(examination_service, "uuid4", lambda: examination_id)
    session = MagicMock()

    examination, created_patient = await examination_service.upload_examination(
        session,
        patient_id=patient_id,
        generate_patient=False,
        uploaded_by=uuid4(),
        file=UploadFile(filename="recording.eeg", file=BytesIO(b"eeg")),
        timestamps=[0, 83456],
    )

    recording_key = f"examinations/{patient_id}/{examination_id}/recording.eeg"
    assert created_patient is False
    assert examination.storage_key == recording_key
    assert uploads[recording_key] == (b"eeg", None)
    assert uploads[examination_service.timestamps_storage_key(recording_key)] == (
        b'{"timestamps": [0, 83456]}',
        "application/json",
    )
