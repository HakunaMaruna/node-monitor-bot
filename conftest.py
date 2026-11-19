import os

os.environ.setdefault("BOT_TOKEN", "123456:TEST_TOKEN")
os.environ.setdefault("ADMIN_ID", "1")

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.services.nodes as nodes
from app.database import Base


@pytest.fixture
async def node_db(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(nodes, "async_session", async_sessionmaker(engine, expire_on_commit=False))
    yield
    await engine.dispose()
