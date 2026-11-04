from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+psycopg://retinopathy:retinopathy@localhost:5432/retinopathy"
    )
    max_upload_bytes: int = 10 * 1024 * 1024
    min_image_width: int = 64
    min_image_height: int = 64
    supported_media_types: tuple[str, ...] = ("image/jpeg", "image/png")
    model_version: str = "prototype-0.1.0"
    model_name: str = "cpu-dummy"
    confidence_threshold: float = Field(default=0.60, ge=0, le=1)
    enable_audit_events: bool = False

    model_config = SettingsConfigDict(env_prefix="RETINOPATHY_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
