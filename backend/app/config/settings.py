from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime settings with safe local-development defaults."""

    model_config = SettingsConfigDict(
        env_prefix="EMAIL_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Email Receiving Platform"
    environment: str = "development"
    database_url: str = Field(
        default=f"sqlite:///{(PROJECT_ROOT / 'data' / 'database.sqlite').as_posix()}"
    )
    data_dir: Path = PROJECT_ROOT / "data"
    names_dir: Path = PROJECT_ROOT / "data" / "names"
    log_dir: Path = PROJECT_ROOT / "logs"
    allowed_domain: str = "example.test"
    max_emails_per_mailbox: int = 10
    jwt_secret_key: str = "development-only-change-this-secret-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
