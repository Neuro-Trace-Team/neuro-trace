from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "ML Microservice"

    queue_url: str = "amqp://guest:guest@localhost/"
    queue_name: str = "ml_microservice_queue"

    model_path: str = "src/models/weights/model.joblib"

    backend_base_url: str = ""
    backend_email: str = "example@example.com"
    backend_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
