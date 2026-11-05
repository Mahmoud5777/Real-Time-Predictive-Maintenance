
from pydantic_settings import BaseSettings, SettingsConfigDict


class FogConfig(BaseSettings):
    """Configuration of a Fog Node."""

    model_config = SettingsConfigDict(
        env_prefix="FOG_",
        env_file=".env",
        extra="ignore"
    )

    fog_id: str = "fog-a"
    zone: str = "A"

    host: str = "0.0.0.0"
    port: int = 8001

    max_queue_size: int = 100

    cpu_threshold: float = 80.0
    ram_threshold: float = 80.0

    temperature_threshold: float = 80.0
    vibration_threshold: float = 5.0


config = FogConfig()
