from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration chargee depuis les variables d environnement (.env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://fog:fog@localhost:5432/fog_cloud",
        description="URL SQLAlchemy async vers PostgreSQL",
    )
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_client_id: str = "fog-cloud-ingest"
    mqtt_qos: int = 1

    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    ingest_token: str = "change-me-in-env"

    raw_retention_days: int = 7
    kpi_refresh_seconds: int = 60
    heartbeat_timeout_seconds: int = 15

    log_level: str = "INFO"


settings = Settings()
get_settings = lambda: settings  # noqa: E731 - acces unique et previsible a la configuration

