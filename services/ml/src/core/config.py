from urllib.parse import quote

from pydantic import AliasChoices, Field
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
    queue_name: str = Field(
        default="ml_microservice_queue",
        validation_alias=AliasChoices("QUEUE_NAME", "RABBITMQ_QUEUE"),
    )

    model_path: str = "src/models/weights/model.joblib"

    backend_base_url: str = ""
    backend_email: str = "example@example.com"
    backend_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def queue_url(self) -> str:
        if self.queue_url_override:
            return self.queue_url_override

        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password, safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"

settings = Settings()
