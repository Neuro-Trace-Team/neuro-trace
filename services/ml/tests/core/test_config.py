import pytest
from pydantic import ValidationError

from core.config import Settings

ENV_KEYS = [
    "RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASSWORD",
    "QUEUE_URL", "RABBITMQ_URL",
    "PENDING_ANALYSIS_QUEUE_NAME", "RABBITMQ_PENDING_ANALYSIS_QUEUE",
    "COMPLETED_ANALYSIS_QUEUE_NAME", "RABBITMQ_COMPLETED_ANALYSIS_QUEUE",
]


@pytest.fixture
def make_settings(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MODEL_DB_URL", "postgresql+asyncpg://u:p@h/db")

    def _make(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return Settings(_env_file=None)

    return _make


def test_default_queue_url(make_settings):
    assert make_settings().queue_url == "amqp://guest:guest@localhost:5672/"


def test_queue_url_is_built_from_rabbitmq_parts(make_settings):
    s = make_settings(RABBITMQ_HOST="mq", RABBITMQ_PORT="5673",
                      RABBITMQ_USER="bob", RABBITMQ_PASSWORD="secret")
    assert s.queue_url == "amqp://bob:secret@mq:5673/"


def test_credentials_are_percent_encoded(make_settings):
    s = make_settings(RABBITMQ_USER="u@x", RABBITMQ_PASSWORD="p/w:rd")
    assert s.queue_url == "amqp://u%40x:p%2Fw%3Ard@localhost:5672/"


@pytest.mark.parametrize("var", ["QUEUE_URL", "RABBITMQ_URL"])
def test_explicit_url_overrides_parts(make_settings, var):
    s = make_settings(**{var: "amqp://override/"}, RABBITMQ_HOST="ignored")
    assert s.queue_url == "amqp://override/"


def test_queue_names_differ_by_default(make_settings):
    s = make_settings()
    assert s.pending_analysis_queue_name != s.completed_queue_name


def test_queue_names_accept_both_env_aliases(make_settings):
    s = make_settings(PENDING_ANALYSIS_QUEUE_NAME="p", RABBITMQ_COMPLETED_ANALYSIS_QUEUE="c")
    assert (s.pending_analysis_queue_name, s.completed_queue_name) == ("p", "c")


def test_identical_queue_names_are_rejected(make_settings):
    with pytest.raises(ValidationError, match="must differ"):      # needs the validator above
        make_settings(PENDING_ANALYSIS_QUEUE_NAME="same", COMPLETED_ANALYSIS_QUEUE_NAME="same")


def test_database_url_is_required(make_settings, monkeypatch):
    monkeypatch.delenv("MODEL_DB_URL")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("url", ["postgresql://u:p@h/db", "sqlite+aiosqlite://"])
def test_database_url_must_use_asyncpg(make_settings, url):
    with pytest.raises(ValidationError, match="asyncpg"):
        make_settings(MODEL_DB_URL=url)


@pytest.mark.parametrize("var", [
    "PENDING_ANALYSIS_QUEUE_NAME", "RABBITMQ_PENDING_ANALYSIS_QUEUE",
    "COMPLETED_ANALYSIS_QUEUE_NAME", "RABBITMQ_COMPLETED_ANALYSIS_QUEUE",
])
def test_empty_queue_name_is_rejected(make_settings, var):
    with pytest.raises(ValidationError):
        make_settings(**{var: ""})


def test_first_alias_wins_when_both_are_set(make_settings):
    s = make_settings(PENDING_ANALYSIS_QUEUE_NAME="first",
                      RABBITMQ_PENDING_ANALYSIS_QUEUE="second")
    assert s.pending_analysis_queue_name == "first"