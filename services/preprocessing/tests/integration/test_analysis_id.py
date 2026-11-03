from unittest.mock import Mock
from uuid import uuid4

import pytest

from service.jobs import JobManager


def test_job_preserves_backend_examination_id_until_publication(backend_client, monkeypatch):
    backend = Mock()
    storage = Mock()
    manager = JobManager(backend_client.settings, storage, backend)
    examination_id = str(uuid4())
    job_id = manager.create(examination_id)
    backend.get_job.return_value = {"status": "QUEUED", "examination_id": examination_id}
    backend.get_examination.return_value = {"source_file": {"bucket": "exam-bucket"}}
    monkeypatch.setattr("service.jobs.subprocess.run", Mock(return_value=Mock(
        returncode=0, stdout="", stderr=""
    )))
    publish = Mock(return_value=2)
    monkeypatch.setattr("service.jobs.publish_combined_features", publish)

    manager.run(job_id, examination_id)

    assert manager.get(job_id)["examination_id"] == examination_id
    assert manager.get(job_id)["status"] == "COMPLETED"
    assert publish.call_args.kwargs == {"examination_id": examination_id}
    backend.submit_result.assert_called_once_with(
        job_id, "COMPLETED", output_bucket="exam-bucket",
        output_storage_key=f"preprocessing/{examination_id}/{job_id}/combined_features.csv",
    )


@pytest.mark.parametrize("examination_id", [None, "bucket/path", "invalid"])
def test_job_rejects_missing_or_invalid_examination_id(backend_client, examination_id):
    manager = JobManager(backend_client.settings, Mock(), backend_client)
    with pytest.raises(ValueError, match="examination_id"):
        manager.create(examination_id)


def test_mismatched_backend_examination_id_stops_publication(backend_client, monkeypatch):
    backend, storage = Mock(), Mock()
    manager = JobManager(backend_client.settings, storage, backend)
    examination_id = str(uuid4())
    job_id = manager.create(examination_id)
    backend.get_job.return_value = {"status": "QUEUED", "examination_id": str(uuid4())}
    publish = Mock()
    monkeypatch.setattr("service.jobs.publish_combined_features", publish)

    manager.run(job_id, examination_id)

    assert manager.get(job_id)["status"] == "FAILED"
    publish.assert_not_called()
    storage.download_examination.assert_not_called()
