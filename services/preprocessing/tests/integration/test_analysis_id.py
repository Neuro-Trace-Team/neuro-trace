from unittest.mock import Mock
from uuid import uuid4

import pytest

from service.jobs import JobManager


def test_processing_uses_examination_id_without_a_job_id(pipeline_job):
    manager, examination_id, storage, process, publish, root, output = pipeline_job
    manager.run(examination_id)
    job = manager.get(examination_id)
    assert job['examination_id'] == examination_id
    assert job['status'] == 'COMPLETED'
    assert 'job_id' not in job
    assert publish.call_args.kwargs == {'examination_id': examination_id}


@pytest.mark.parametrize("examination_id", [None, "bucket/path", "invalid"])
def test_job_rejects_missing_or_invalid_examination_id(backend_client, examination_id):
    manager = JobManager(backend_client.settings, Mock(), backend_client)
    with pytest.raises(ValueError, match="examination_id"):
        manager.create(examination_id, storage_bucket="bucket", storage_key="source.bdf")


@pytest.mark.parametrize(
    ("storage_bucket", "storage_key", "message"),
    [("", "source.bdf", "storage_bucket"), ("bucket", "", "storage_key")],
)
def test_job_rejects_missing_storage_coordinates(
    backend_client, storage_bucket, storage_key, message
):
    manager = JobManager(backend_client.settings, Mock(), backend_client)
    with pytest.raises(ValueError, match=message):
        manager.create(
            str(uuid4()), storage_bucket=storage_bucket, storage_key=storage_key
        )
