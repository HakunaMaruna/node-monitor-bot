from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.intervals import interval_seconds


def naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    ip: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=5)
    expected_response: Mapped[str | None] = mapped_column(String, nullable=True)
    check_interval: Mapped[int] = mapped_column(Integer, default=1)
    check_interval_unit: Mapped[str] = mapped_column(String, default="m")

    last_status: Mapped[bool] = mapped_column(Boolean, default=True)
    last_notified_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    last_check_time: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
    status_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    last_alert_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    blocked: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    blocked_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    check_history: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    @property
    def interval_seconds(self) -> int:
        return interval_seconds(self.check_interval, self.check_interval_unit)
