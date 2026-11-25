from urllib.parse import quote
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "ML Microservice"

    rabbitmq_host: str = Field(default="localhost", validation_alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, validation_alias="RABBITMQ_PORT")
    rabbitmq_user: str = Field(default="guest", validation_alias="RABBITMQ_USER")
    rabbitmq_password: str = Field(default="guest", validation_alias="RABBITMQ_PASSWORD")

    queue_url_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("QUEUE_URL", "RABBITMQ_URL"),
    )
    pending_analysis_queue_name: str = Field(
        default="ml_microservice_pending_queue", min_length=1,
        validation_alias=AliasChoices("PENDING_ANALYSIS_QUEUE_NAME", "RABBITMQ_PENDING_ANALYSIS_QUEUE"),
    )
    completed_queue_name: str = Field(
        default="ml_microservice_completed_queue", min_length=1,
        validation_alias=AliasChoices("COMPLETED_ANALYSIS_QUEUE_NAME", "RABBITMQ_COMPLETED_ANALYSIS_QUEUE"),
    )

    model_path: str = Field(default="/app/models/lgbm_v3_2026-11-22.joblib", validation_alias="MODEL_PATH")
    cqr_base_path: str | None = Field(default=None, validation_alias="CQR_BASE_PATH")
    
    database_url: str = Field(validation_alias="MODEL_DB_URL")

    database_url: str = Field(validation_alias="MODEL_DB_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    max_missing_feature_fraction: float = Field(
        default=1.0, ge=0.0, le=1.0, validation_alias="MAX_MISSING_FEATURE_FRACTION",
    )

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

    @model_validator(mode="after")
    def _queues_must_differ(self) -> "Settings":
        if self.pending_analysis_queue_name == self.completed_queue_name:
            raise ValueError("pending and completed queue names must differ")
        return self

    @field_validator("cqr_base_path")
    @classmethod
    def _blank_cqr_path_means_disabled(cls, v: str | None) -> str | None:
        return v or None 

settings = Settings()
