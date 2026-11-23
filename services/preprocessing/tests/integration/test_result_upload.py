import json
import subprocess
from unittest.mock import Mock

import pytest

from service.jobs import JobConflictError, JobManager

REAL_SUBPROCESS_RUN = subprocess.run

def test_worker_downloads_from_post_coordinates_without_backend_examination_lookup(pipeline_job):
    manager, eid, storage, process, publish, root, output = pipeline_job
    manager.run(eid)
    job = manager.get(eid)
    assert job['status'] == 'COMPLETED'
    assert job['warnings'] == ['QC warning']
    assert job['data_quality_status'] == 'partial'
    storage.download_recording_inputs.assert_called_once_with(
        'exam-bucket', 'exam/recording.bdf', root / 'input/study/subject/run')
    assert storage.upload_result.call_args_list[0].args == (
        output / 'preprocessing_report.json', 'exam-bucket', f'preprocessing/{eid}/preprocessing_report.json')
    assert storage.upload_result.call_args_list[1].args == (
        output / 'combined_features.csv', 'exam-bucket', f'preprocessing/{eid}/combined_features.csv')
    assert publish.call_args.kwargs == {'examination_id': eid}
    assert process.call_args.kwargs['timeout'] == manager.settings.pipeline_timeout_seconds


@pytest.mark.parametrize('failure', ['exit', 'failed_report', 'missing_report', 'missing_csv',
                                     'empty_csv', 'invalid_time', 'timeout', 'upload', 'rabbitmq'])
def test_worker_failure_never_reports_completion(pipeline_job, failure):
    manager, eid, storage, process, publish, root, output = pipeline_job
    execute = process.side_effect
    def fail(command, **kwargs):
        result = execute(command, **kwargs)
        if failure == 'exit': result.returncode = 1
        if failure == 'failed_report':
            (output / 'preprocessing_report.json').write_text(json.dumps({
                'preprocessing_status': 'failed', 'errors': ['bad BDF']}))
        if failure == 'missing_report': (output / 'preprocessing_report.json').unlink()
        if failure == 'missing_csv': (output / 'combined_features.csv').unlink()
        if failure == 'empty_csv': (output / 'combined_features.csv').write_text('event_time_s\n')
        if failure == 'invalid_time': (output / 'combined_features.csv').write_text('event_time_s\n-1\n')
        return result
    process.side_effect = fail
    if failure == 'timeout': process.side_effect = subprocess.TimeoutExpired('pipeline', 1)
    if failure == 'upload': storage.upload_result.side_effect = RuntimeError('S3 unavailable')
    if failure == 'rabbitmq': publish.side_effect = RuntimeError('broker unavailable')
    manager.run(eid)
    job = manager.get(eid)
    assert job['status'] == 'FAILED'
    assert job['error']
    if failure != 'rabbitmq': publish.assert_not_called()
    if failure not in {'upload', 'rabbitmq'}:
        assert all(call.args[0].name != 'combined_features.csv' for call in storage.upload_result.call_args_list)
    if failure != 'upload': assert job['output_report_key'].endswith('preprocessing_report.json')
    else: assert job['report_upload_error'] == 'S3 unavailable'


def test_empty_timestamps_are_rejected_before_running_pipeline(pipeline_job):
    manager, eid, storage, process, publish, root, output = pipeline_job
    def download(bucket, key, destination):
        destination.mkdir(parents=True)
        (destination / 'timestamps.json').write_text('{"timestamps": []}')
    storage.download_recording_inputs.side_effect = download
    manager.run(eid)
    assert manager.get(eid)['status'] == 'FAILED'
    process.assert_not_called()
    publish.assert_not_called()


def test_active_jobs_conflict_across_managers_and_status_survives_restart(pipeline_job):
    manager, eid, storage, process, publish, root, output = pipeline_job
    other = JobManager(manager.settings, storage)
    assert other.get(eid)['status'] == 'QUEUED'
    with pytest.raises(JobConflictError):
        other.create(eid, storage_bucket='bucket', storage_key='new.edf')
    manager.run(eid)
    assert other.get(eid)['status'] == 'COMPLETED'
    assert other.get(eid)['output_report_key'] == manager.get(eid)['output_report_key']


def test_interrupted_job_is_recovered_as_failed(pipeline_job):
    manager, eid, storage, process, publish, root, output = pipeline_job
    manager._leases.pop(eid).close()  # Simulate OS releasing the lock on process exit.
    restarted = JobManager(manager.settings, storage)
    assert restarted.get(eid)['status'] == 'FAILED'
    assert 'interrupted' in restarted.get(eid)['error']


def test_retry_cannot_publish_previous_attempt_csv(pipeline_job):
    manager, eid, storage, process, publish, root, output = pipeline_job
    manager.run(eid)
    old_attempt = manager.get(eid)['attempt_id']
    manager.create(eid, storage_bucket='exam-bucket', storage_key='new.edf')
    assert manager.get(eid)['attempt_id'] != old_attempt
    process.side_effect = None
    process.return_value = Mock(returncode=0, stdout='', stderr='')
    publish.reset_mock()
    manager.run(eid)
    assert manager.get(eid)['status'] == 'FAILED'
    assert 'did not produce' in manager.get(eid)['error']
    publish.assert_not_called()
    assert (output / 'combined_features.csv').exists()


@pytest.mark.parametrize(('bucket', 'key'), [(None, 'source.bdf'), ('bucket', None)])
def test_manager_rejects_missing_storage_coordinate(backend_client, bucket, key):
    manager = JobManager(backend_client.settings, Mock())
    from uuid import uuid4
    with pytest.raises(ValueError, match='provided together'):
        manager.create(str(uuid4()), storage_bucket=bucket, storage_key=key)


@pytest.mark.parametrize('report', ['{bad json', '[]', 'null'])
def test_malformed_pipeline_report_fails_with_persisted_diagnostics(pipeline_job, report):
    manager, eid, storage, process, publish, root, output = pipeline_job
    execute = process.side_effect
    def malformed(command, **kwargs):
        result = execute(command, **kwargs)
        (output / 'preprocessing_report.json').write_text(report)
        return result
    process.side_effect = malformed
    manager.run(eid)
    assert manager.get(eid)['status'] == 'FAILED'
    assert json.loads((output / 'preprocessing_report.json').read_text())['service_status'] == 'FAILED'
    publish.assert_not_called()


def test_real_cli_failure_with_stale_csv_is_not_published(pipeline_job):
    manager, eid, storage, process, publish, root, output = pipeline_job
    process.side_effect = REAL_SUBPROCESS_RUN
    output.mkdir(parents=True)
    (output / 'combined_features.csv').write_text('event_time_s\n10\n')
    # Fixture downloads a deliberately invalid BDF; the real CLI returns 0 with a failed report.
    manager.run(eid)
    assert manager.get(eid)['status'] == 'FAILED'
    assert 'Pipeline failed' in manager.get(eid)['error']
    publish.assert_not_called()
    assert all(call.args[0].suffix == '.json' for call in storage.upload_result.call_args_list)
