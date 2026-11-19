from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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

    last_status: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check_time: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
