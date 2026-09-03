"""Application settings, loaded from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://pulsevault:pulsevault@db:5432/pulsevault"

    # App auth (single user)
    app_username: str = "admin"
    app_password: str = "admin"
    app_secret_key: str = "dev-insecure-change-me"

    # Device push ingestion (the desktop companion agent uploads FIT files).
    # A static bearer token the agent sends; leave blank to auto-generate at boot.
    ingest_token: str = ""

    # Internal watch-app build service (compiles a pre-configured Vaultwrist .prg).
    builder_url: str = "http://builder:8080"

    # Directory holding the prebuilt companion binaries (mounted on the server).
    companion_dist_dir: str = "/companion-dist"

    # Garmin Connect
    garmin_email: str = ""
    garmin_password: str = ""
    garth_home: str = "/data/garth"

    # Sync behaviour
    sync_interval_minutes: int = 180
    initial_backfill_days: int = 30

    tz: str = "UTC"


settings = Settings()
