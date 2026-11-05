from pydantic_settings import BaseSettings, SettingsConfigDict


class FogConfig(BaseSettings):

    model_config = SettingsConfigDict(
        env_prefix="FOG_",
        env_file=".env",
        extra="ignore"
    )

    fog_id: str = "fog-b"
    zone: str = "B"
    host: str = "0.0.0.0"
    port: int = 8002

    max_queue_size: int = 100

    cpu_threshold: float = 75.0
    ram_threshold: float = 75.0

    temperature_threshold: float = 80.0
    vibration_threshold: float = 5.0


config = FogConfig()