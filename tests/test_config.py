import pytest
from pydantic import ValidationError

from app.config import Settings


def test_intervals_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, POLL_TICK_SECONDS=0)

    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, SUMMARY_INTERVAL_HOURS=0)

    with pytest.raises(ValidationError):
        Settings(BOT_TOKEN="123456:TEST_TOKEN", ADMIN_ID=1, CHEBURCHECK_INTERVAL_HOURS=0)
