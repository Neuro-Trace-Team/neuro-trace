from functools import lru_cache
from urllib.parse import quote

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration supplied by the environment, never by source code."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    db_auth_url: str
    db_medical_url: str
    db_audit_url: str
    rustfs_endpoint: str
    rustfs_access_key: str
    rustfs_secret_key: str
    rustfs_bucket: str = "examinations"
    max_upload_size_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    preprocessing_url: str
    ml_url: str
    service_timeout_seconds: float = Field(default=10, gt=0)
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = Field(default=5672, gt=0)
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    completed_analysis_queue_name: str = Field(
        default="ml_microservice_completed_queue",
        validation_alias=AliasChoices("RABBITMQ_COMPLETED_ANALYSIS_QUEUE", "COMPLETED_ANALYSIS_QUEUE_NAME"),
    )
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=7, gt=0)

    @property
    def rabbitmq_url(self) -> str:
        return "amqp://{}:{}@{}:{}/".format(
            quote(self.rabbitmq_user, safe=""),
            quote(self.rabbitmq_password, safe=""),
            self.rabbitmq_host,
            self.rabbitmq_port,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
