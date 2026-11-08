# tests/core/test_compose_contract.py
import re
from pathlib import Path

import pytest
import yaml

from core.config import Settings

COMPOSE = Path(__file__).parents[4] / "docker-compose.yml"   # repo root; adjust if needed
pytestmark = pytest.mark.skipif(not COMPOSE.exists(), reason="docker-compose.yml not found")

SUBSTITUTIONS = {
    "RABBITMQ_USER": "ruser", "RABBITMQ_PASSWORD": "rpass",
    "PENDING_ANALYSIS_QUEUE_NAME": "q.pending",
    "COMPLETED_ANALYSIS_QUEUE_NAME": "q.completed",
    "ML_SERVICE_TOKEN": "tok", "RABBITMQ_EXCHANGE": "", "RABBITMQ_ROUTING_KEY": "q.pending",
    "RUSTFS_ACCESS_KEY": "a", "RUSTFS_SECRET_KEY": "s", "PREPROCESSING_SERVICE_TOKEN": "t",
    "JWT_SECRET": "j", "PREPROCESSING_SERVICE_JWT_SECRET": "p",
}


def service_env(name):
    compose = yaml.safe_load(COMPOSE.read_text())
    raw = compose["services"][name].get("environment", {})
    return {
        k: re.sub(r"\$\{(\w+)\}", lambda m: SUBSTITUTIONS[m.group(1)], str(v))
        for k, v in raw.items()
    }


@pytest.fixture
def ml_settings(monkeypatch):
    for k, v in service_env("ml").items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)


def test_ml_service_environment_produces_valid_settings(ml_settings):
    assert ml_settings.queue_url == "amqp://ruser:rpass@rabbitmq:5672/"


def test_ml_reads_the_pending_queue_that_preprocessing_publishes_to(ml_settings):
    assert ml_settings.pending_analysis_queue_name == \
        service_env("preprocessing")["RABBITMQ_PENDING_ANALYSIS_QUEUE"]


def test_ml_publishes_to_the_completed_queue_the_backend_consumes(ml_settings):
    assert ml_settings.completed_queue_name == \
        service_env("backend")["RABBITMQ_COMPLETED_ANALYSIS_QUEUE"]