import pytest
from pydantic import ValidationError

from app.config import Settings


def test_alert_repeat_minutes_allows_zero():
    settings = Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, ALERT_REPEAT_MINUTES=0)
    assert settings.ALERT_REPEAT_MINUTES == 0


def test_intervals_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, POLL_TICK_SECONDS=0)

    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, SUMMARY_INTERVAL_HOURS=0)

    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, CHEBURCHECK_INTERVAL_HOURS=0)

    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, CHEBURCHECK_STARTUP_DELAY_SEC=0)

    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, ALERT_REPEAT_MINUTES=-1)


def test_cheburcheck_base_url_must_be_https():
    with pytest.raises(ValidationError):
        Settings(
            BOT_TOKEN="123456:TEST_TOKEN",
            ADMIN_ID=1,
            CHEBURCHECK_BASE_URL="http://cheburcheck.ru/api/v1",
        )

    settings = Settings(
        BOT_TOKEN="123456:TEST_TOKEN",
        ADMIN_ID=1,
        CHEBURCHECK_BASE_URL="https://cheburcheck.ru/api/v1/",
    )
    assert settings.CHEBURCHECK_BASE_URL == "https://cheburcheck.ru/api/v1"


def test_block_private_targets_defaults_to_false():
    settings = Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1)
    assert settings.BLOCK_PRIVATE_TARGETS is False
