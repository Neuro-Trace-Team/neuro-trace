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
            examination_date=None,
        )
    session.add.assert_not_called()
