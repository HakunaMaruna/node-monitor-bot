from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_ID: int
    DB_URL: str = "sqlite+aiosqlite:///./nodes.db"

    ALERT_CHAT_ID: int | None = None
    SUMMARY_CHAT_ID: int | None = None

    DEFAULT_CHECK_INTERVAL: int = 5
    SUMMARY_INTERVAL_HOURS: int = 1

    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("ALERT_CHAT_ID", "SUMMARY_CHAT_ID", mode="before")
    @classmethod
    def empty_chat_id_is_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


settings = Settings()
