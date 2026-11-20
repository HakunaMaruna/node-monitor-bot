from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_ID: int
    DB_URL: str = "sqlite+aiosqlite:///./nodes.db"

    ALERT_CHAT_ID: int | None = None
    SUMMARY_CHAT_ID: int | None = None
    ALERT_REPEAT_MINUTES: int = Field(default=15, ge=0)

    POLL_TICK_SECONDS: int = Field(default=1, gt=0)
    SUMMARY_INTERVAL_HOURS: int = Field(default=1, gt=0)
    CHEBURCHECK_INTERVAL_HOURS: int = Field(default=6, gt=0)
    CHEBURCHECK_STARTUP_DELAY_SEC: int = Field(default=10, gt=0)
    CHEBURCHECK_TIMEOUT_SEC: int = Field(default=10, gt=0)
    CHEBURCHECK_REQUEST_DELAY_SEC: float = Field(default=2.1, gt=0)
    CHEBURCHECK_BASE_URL: str = "https://cheburcheck.ru/api/v1"
    CHEBURCHECK_API_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("ALERT_CHAT_ID", "SUMMARY_CHAT_ID", mode="before")
    @classmethod
    def empty_chat_id_is_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


settings = Settings()
