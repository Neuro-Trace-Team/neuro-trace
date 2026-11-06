from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4
import json

import pytest

from service.jobs import JobManager
from service.storage import RustFSStorage


@pytest.mark.parametrize('failure', [None, 'pipeline', 'missing_csv', 'bucket', 'upload', 'rabbitmq', 'callback'])
def test_upload_lifecycle(backend_client, monkeypatch, failure):
    backend = Mock()
    storage = RustFSStorage(backend_client.settings)
    client = Mock()
    monkeypatch.setattr(storage, '_client', lambda: client)
    monkeypatch.setattr(storage, 'download_examination', Mock())
    manager = JobManager(backend_client.settings, storage, backend)
    examination_id = str(uuid4())
    job_id = manager.create(examination_id)
    backend.get_job.return_value = {'status': 'QUEUED', 'examination_id': examination_id}
    backend.get_examination.return_value = {'source_file': {'bucket': '' if failure == 'bucket' else 'backend-bucket'}}
    output = backend_client.settings.work_root / job_id / 'output/study/subject/run/combined_features.csv'
    key = f'preprocessing/{examination_id}/{job_id}/combined_features.csv'
    events = []

    def pipeline(*args, **kwargs):
        if failure != 'missing_csv':
            output.parent.mkdir(parents=True)
            output.write_bytes(b'feature\n1\n')
        return Mock(returncode=int(failure == 'pipeline'), stdout='', stderr='failed')

    def upload(path, bucket, storage_key):
        assert (path, bucket, storage_key) == (str(output), 'backend-bucket', key)
        assert Path(path).read_bytes() == b'feature\n1\n'
        events.append('upload')
        if failure == 'upload':
            raise RuntimeError('upload failed')

    def publish(*args, **kwargs):
        assert events == ['upload']
        events.append('publish')
        if failure == 'rabbitmq':
            raise RuntimeError('broker failed')
        return 1

    def callback(id_, status, **kwargs):
        if status == 'COMPLETED':
            assert events == ['upload', 'publish']
            assert manager.get(job_id)['status'] == 'RUNNING'
            if failure == 'callback':
                raise RuntimeError('callback failed')

    monkeypatch.setattr('service.jobs.subprocess.run', pipeline)
    publisher = Mock(side_effect=publish)
    monkeypatch.setattr('service.jobs.publish_combined_features', publisher)
    client.upload_file.side_effect = upload
    backend.submit_result.side_effect = callback
    manager.run(job_id, examination_id)

    assert manager.get(job_id)['status'] == ('FAILED' if failure else 'COMPLETED')
    if failure in {'pipeline', 'missing_csv', 'bucket'}:
        client.upload_file.assert_not_called()
    if failure in {'pipeline', 'missing_csv', 'bucket', 'upload'}:
        publisher.assert_not_called()
    if failure:
        assert backend.submit_result.call_args.args == (job_id, 'FAILED')
    else:
        backend.submit_result.assert_called_once_with(job_id, 'COMPLETED', output_bucket='backend-bucket', output_storage_key=key)
        assert manager.get(job_id)['output_storage_key'] == key


def test_result_callback_payload(backend_client, monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=Mock(read=Mock(return_value=b'{}')))
    response.__exit__ = Mock(return_value=False)
    request = Mock(return_value=response)
    monkeypatch.setattr('service.jobs.urlopen', request)
    backend_client.submit_result('job', 'COMPLETED', output_bucket='bucket', output_storage_key='result.csv')
    assert json.loads(request.call_args.args[0].data) == {
        'status': 'COMPLETED', 'output_bucket': 'bucket', 'output_storage_key': 'result.csv',
    }
    backend_client.submit_result('job', 'FAILED', error_message='upload failed')
    assert json.loads(request.call_args.args[0].data) == {'status': 'FAILED', 'error_message': 'upload failed'}


def test_worker_downloads_from_post_coordinates_without_backend_examination_lookup(
    backend_client, monkeypatch
):
    backend = Mock()
    storage = Mock()
    manager = JobManager(backend_client.settings, storage, backend)
    examination_id = str(uuid4())
    bucket = "backend-bucket"
    storage_key = f"examinations/patient/{examination_id}/recording.bdf"
    job_id = manager.create(
        examination_id,
        storage_bucket=bucket,
        storage_key=storage_key,
    )
    backend.get_job.return_value = {
        "status": "QUEUED",
        "examination_id": examination_id,
    }
    output = backend_client.settings.work_root / job_id / "output/study/subject/run/combined_features.csv"

    def pipeline(*args, **kwargs):
        output.parent.mkdir(parents=True)
        output.write_bytes(b"feature\n1\n")
        return Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("service.jobs.subprocess.run", pipeline)
    monkeypatch.setattr("service.jobs.publish_combined_features", Mock(return_value=1))

    manager.run(job_id, examination_id)

    storage.download_recording_inputs.assert_called_once_with(
        bucket,
        storage_key,
        backend_client.settings.work_root / job_id / "input/study/subject/run",
    )
    backend.get_examination.assert_not_called()
    backend.submit_result.assert_called_once_with(
        job_id,
        "COMPLETED",
        output_bucket=bucket,
        output_storage_key=f"preprocessing/{examination_id}/{job_id}/combined_features.csv",
    )
