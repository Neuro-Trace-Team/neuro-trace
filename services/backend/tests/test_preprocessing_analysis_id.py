from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from src.models.medical import Analysis
from src.services import preprocessing_jobs


@pytest.mark.parametrize("service_caller", [False, True])
def test_job_and_analysis_are_created_in_one_transaction(monkeypatch, service_caller):
    session = Mock()
    examination_id, uploader_id, user_id = uuid4(), uuid4(), uuid4()
    examination = SimpleNamespace(uploaded_by=uploader_id)
    monkeypatch.setattr(preprocessing_jobs.examinations_service, "get_examination",
                        Mock(return_value=examination))

    job = preprocessing_jobs.create_preprocessing_job(
        session, examination_id=examination_id, pipeline_version="test",
        parameters={"analysis_id": "untrusted", "option": 1},
        requested_by=None if service_caller else user_id,
    )

    analysis = session.add.call_args_list[1].args[0]
    assert isinstance(analysis, Analysis)
    assert analysis.id == UUID(job.parameters_json["analysis_id"])
    assert analysis.preprocessing_job_id == job.id
    assert analysis.examination_id == examination_id
    assert analysis.requested_by == (uploader_id if service_caller else user_id)
    assert analysis.status == "QUEUED"
    assert job.parameters_json["option"] == 1
    session.flush.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(job)
