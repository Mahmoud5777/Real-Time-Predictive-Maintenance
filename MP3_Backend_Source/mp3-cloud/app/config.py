from pydantic import Field, model_validator
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

    raw_retention_days: int = Field(default=7, ge=1, le=365)
    kpi_refresh_seconds: int = Field(default=60, ge=10, le=3600)
    kpi_lookback_hours: int = Field(default=24, ge=1, le=744)
    kpi_database_timeout_seconds: float = Field(default=30, gt=0, le=300)
    kpi_metrics_host: str = "127.0.0.1"
    kpi_metrics_port: int = Field(default=8002, ge=0, le=65535)
    heartbeat_timeout_seconds: int = Field(default=15, ge=1, le=3600)
    heartbeat_clock_skew_seconds: int = Field(default=5, ge=0, le=60)
    supervision_interval_seconds: int = Field(default=5, ge=1, le=60)
    supervision_database_timeout_seconds: float = Field(default=10, gt=0, le=120)
    supervision_gap_seconds: int = Field(default=30, ge=2, le=3600)
    supervision_metrics_host: str = "127.0.0.1"
    supervision_metrics_port: int = Field(default=8003, ge=0, le=65535)
    retention_interval_seconds: int = Field(default=60, ge=10, le=3600)
    retention_database_timeout_seconds: float = Field(default=30, gt=0, le=300)
    retention_batch_size: int = Field(default=1000, ge=1, le=10000)
    retention_dry_run: bool = True
    retention_metrics_host: str = "127.0.0.1"
    retention_metrics_port: int = Field(default=8004, ge=0, le=65535)

    log_level: str = "INFO"

    @model_validator(mode="after")
    def valid_kpi_horizon(self):
        if self.kpi_lookback_hours > self.raw_retention_days * 24:
            raise ValueError("KPI_LOOKBACK_HOURS exceeds RAW_RETENTION_DAYS")
        if self.supervision_gap_seconds < max(
            2 * self.supervision_interval_seconds,
            self.supervision_interval_seconds + self.supervision_database_timeout_seconds,
        ):
            raise ValueError("SUPERVISION_GAP_SECONDS must cover interval and database timeout")
        return self


settings = Settings()
get_settings = lambda: settings  # noqa: E731 - acces unique et previsible a la configuration
