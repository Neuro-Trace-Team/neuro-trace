from functools import lru_cache

from pydantic import Field
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
    jwt_secret: str = Field(min_length=32)
    preprocessing_service_jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=7, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
