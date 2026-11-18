from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from service.config import Settings
from service.rabbitmq import publish_combined_features


@pytest.mark.parametrize(('environment', 'queue', 'routing'), [
    ({}, 'preprocessing.combined_features', 'preprocessing.combined_features'),
    ({'RABBITMQ_PENDING_ANALYSIS_QUEUE': 'ml.pending'}, 'ml.pending', 'ml.pending'),
    ({'RABBITMQ_QUEUE': 'explicit', 'RABBITMQ_PENDING_ANALYSIS_QUEUE': 'alias'}, 'explicit', 'explicit'),
    ({'RABBITMQ_PENDING_ANALYSIS_QUEUE': 'ml.pending', 'RABBITMQ_ROUTING_KEY': ''}, 'ml.pending', 'ml.pending'),
    ({'RABBITMQ_QUEUE': '', 'RABBITMQ_PENDING_ANALYSIS_QUEUE': 'ml.pending'}, 'ml.pending', 'ml.pending'),
    ({'RABBITMQ_PENDING_ANALYSIS_QUEUE': 'ml.pending', 'RABBITMQ_ROUTING_KEY': 'features.*'}, 'ml.pending', 'features.*'),
])
def test_compose_queue_alias_and_routing_defaults(monkeypatch, environment, queue, routing):
    for name in ('RABBITMQ_QUEUE', 'RABBITMQ_PENDING_ANALYSIS_QUEUE', 'RABBITMQ_ROUTING_KEY'):
        monkeypatch.delenv(name, raising=False)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    settings = Settings.from_environment()
    assert settings.rabbitmq_queue == queue
    assert settings.rabbitmq_routing_key == routing


@pytest.mark.parametrize('csv', [
    'event_time_s,alpha_power\n',
    'alpha_power\n0.42\n',
    'event_time_s\n-1\n',
    'event_time_s\nnan\n',
    'event_time_s\ninf\n',
    'event_time_s\ninvalid\n',
    'event_time_s\n10\n10\n',
])
def test_invalid_analysis_envelope_never_connects_to_broker(monkeypatch, tmp_path, csv):
    connection = AsyncMock()
    monkeypatch.setattr('service.rabbitmq.aio_pika.connect_robust', connection)
    path = tmp_path / 'combined_features.csv'
    path.write_text(csv)
    with pytest.raises(ValueError):
        publish_combined_features(Settings.from_environment(), path, examination_id=str(uuid4()))
    connection.assert_not_called()
