"""Settings from environment variables, with safe local defaults (SPEC 1.3, 1.4)."""

from pathlib import Path

from pydantic_settings import BaseSettings

DEV_APP_PASSWORD = "dev-password"
DEV_SESSION_SECRET = "dev-session-secret-change-me"


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://woodshed:woodshed@localhost:5432/woodshed"
    APP_PASSWORD: str = DEV_APP_PASSWORD
    SESSION_SECRET: str = DEV_SESSION_SECRET
    MEDIA_DIR: Path = Path(".media")
    LOG_LEVEL: str = "INFO"
    MAX_ATTACHMENT_BYTES: int = 100 * 1024 * 1024  # 100 MB
    MAX_TAKE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    MB_USER_AGENT: str = "woodshed/1.0 (https://guitar.home.cedricschippers.dev)"


def check_production(settings: Settings) -> None:
    """Refuse to start in production with development secrets (SPEC 1.4)."""
    if settings.APP_ENV != "production":
        return
    if settings.APP_PASSWORD == DEV_APP_PASSWORD:
        raise RuntimeError("APP_ENV=production but APP_PASSWORD has its development default")
    if settings.SESSION_SECRET == DEV_SESSION_SECRET or len(settings.SESSION_SECRET) < 32:
        raise RuntimeError("APP_ENV=production needs a SESSION_SECRET of at least 32 characters")
