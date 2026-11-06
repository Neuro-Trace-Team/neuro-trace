from urllib.parse import quote

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "ML Microservice"

    # RabbitMQ settings use the same RABBITMQ_* environment variables as the
    # other services. QUEUE_URL/QUEUE_NAME remain supported as explicit ML
    # overrides for local runs.
    rabbitmq_host: str = Field(default="localhost", validation_alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, validation_alias="RABBITMQ_PORT")
    rabbitmq_user: str = Field(default="guest", validation_alias="RABBITMQ_USER")
    rabbitmq_password: str = Field(default="guest", validation_alias="RABBITMQ_PASSWORD")

    queue_url_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("QUEUE_URL", "RABBITMQ_URL"),
    )
    pending_analysis_queue_name: str = Field(
        default="ml_microservice_pending_queue",
        validation_alias=AliasChoices("PENDING_ANALYSIS_QUEUE_NAME", "RABBITMQ_PENDING_ANALYSIS_QUEUE"),
    )
    completed_queue_name: str = Field(
        default="ml_microservice_completed_queue",
        validation_alias=AliasChoices("COMPLETED_ANALYSIS_QUEUE_NAME", "RABBITMQ_COMPLETED_ANALYSIS_QUEUE"),
    )

    model_path: str = "/app/models/model.joblib"

    backend_base_url: str = Field(
        default="http://backend:8080",
        validation_alias=AliasChoices("BACKEND_URL", "BACKEND_BASE_URL"),
    )
    backend_service_token: str = Field(
        default="",
        validation_alias=AliasChoices("ML_SERVICE_TOKEN", "BACKEND_TOKEN"),
    )

    database_url: str = Field(validation_alias="MODEL_DB_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def queue_url(self) -> str:
        if self.queue_url_override:
            return self.queue_url_override

        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password, safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"

    @field_validator("database_url")
    @classmethod
    def _require_asyncpg_driver(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("MODEL_DB_URL must start with postgresql+asyncpg://")
        return v

settings = Settings()
