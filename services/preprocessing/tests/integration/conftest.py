"""Shared setup for local integration tests using mocked dependencies."""

from __future__ import annotations

import sys
import types

import pytest

try:
    import aio_pika  # noqa: F401
except ModuleNotFoundError:
    # The broker is mocked in these tests, so the runtime client library is
    # not needed merely to import the adapter modules.
    aio_pika_stub = types.ModuleType("aio_pika")

    class _DeliveryMode:
        PERSISTENT = 2

    class _ExchangeType:
        TOPIC = "topic"

    class _Message:
        def __init__(self, body, **kwargs):
            self.body = body
            self.__dict__.update(kwargs)

    async def _connect_robust(*args, **kwargs):
        raise RuntimeError("connect_robust must be mocked by the test")

    aio_pika_stub.DeliveryMode = _DeliveryMode
    aio_pika_stub.ExchangeType = _ExchangeType
    aio_pika_stub.Message = _Message
    aio_pika_stub.connect_robust = _connect_robust
    sys.modules["aio_pika"] = aio_pika_stub


@pytest.fixture
def backend_client(tmp_path):
    from service.config import Settings
    from service.jobs import NeuroTraceClient

    return NeuroTraceClient(
        Settings(
            backend_url="http://mock-backend",
            backend_token="mock-service-token",
            backend_timeout_seconds=2,
            rustfs_endpoint_url="http://mock-rustfs",
            rustfs_access_key_id="access",
            rustfs_secret_access_key="secret",
            rustfs_bucket="examinations",
            work_root=tmp_path,
        )
    )


@pytest.fixture
def pipeline_job(backend_client, monkeypatch):
    """Exercise the real worker contract; replace only external IO and CLI execution."""
    import json
    from pathlib import Path
    from unittest.mock import Mock
    from uuid import uuid4
    from service.jobs import JobManager

    storage = Mock()
    def download(bucket, key, destination):
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'timestamps.json').write_text('{"timestamps": [10000]}')
        (destination / Path(key).name).write_bytes(b'input')
    storage.download_recording_inputs.side_effect = download
    manager = JobManager(backend_client.settings, storage)
    examination_id = str(uuid4())
    manager.create(examination_id, storage_bucket='exam-bucket', storage_key='exam/recording.bdf')
    attempt = manager.get(examination_id)['attempt_id']
    root = backend_client.settings.work_root / examination_id / attempt
    output = root / 'output/study/subject/run'
    def execute(command, **kwargs):
        output.mkdir(parents=True, exist_ok=True)
        (output / 'preprocessing_report.json').write_text(json.dumps({
            'preprocessing_status': 'success', 'data_quality_status': 'partial', 'warnings': ['QC warning']}))
        (output / 'combined_features.csv').write_text('event_time_s,alpha_power\n10,0.42\n')
        return Mock(returncode=0, stdout='done', stderr='')
    process = Mock(side_effect=execute)
    publisher = Mock(return_value=1)
    monkeypatch.setattr('service.jobs.subprocess.run', process)
    monkeypatch.setattr('service.jobs.publish_combined_features', publisher)
    return manager, examination_id, storage, process, publisher, root, output
