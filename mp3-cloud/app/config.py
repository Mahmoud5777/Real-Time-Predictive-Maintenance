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
    mqtt_client_id: str = Field(default="fog-cloud-ingest", min_length=1, max_length=64)
    mqtt_qos: int = Field(default=1, ge=1, le=1)
    mqtt_keepalive_seconds: int = Field(default=30, ge=5, le=3600)
    mqtt_queue_capacity: int = Field(default=256, ge=1, le=10000)
    mqtt_max_payload_bytes: int = Field(default=65536, ge=1024, le=1048576)
    mqtt_retry_seconds: float = Field(default=1, gt=0, le=60)
    mqtt_retry_max_seconds: float = Field(default=30, gt=0, le=300)
    mqtt_connect_timeout_seconds: float = Field(default=5, gt=0, le=60)
    mqtt_database_timeout_seconds: float = Field(default=10, gt=0, le=120)
    mqtt_shutdown_seconds: float = Field(default=15, gt=0, le=120)
    mqtt_metrics_port: int = Field(default=8001, ge=0, le=65535)
    mqtt_metrics_host: str = "127.0.0.1"

    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    ingest_token: str = "change-me-in-env"

    raw_retention_days: int = 7
    kpi_refresh_seconds: int = 60
    heartbeat_timeout_seconds: int = 15

    log_level: str = "INFO"


settings = Settings()
get_settings = lambda: settings  # noqa: E731 - acces unique et previsible a la configuration

