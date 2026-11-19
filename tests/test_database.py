from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

import app.database as database


async def test_init_db_migrates_legacy_nodes_table(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                ip VARCHAR NOT NULL,
                port INTEGER NOT NULL,
                protocol VARCHAR NOT NULL,
                enabled BOOLEAN NOT NULL,
                timeout_sec INTEGER NOT NULL,
                expected_response VARCHAR,
                last_status BOOLEAN NOT NULL,
                last_check_time DATETIME NOT NULL
            )
            """
        )

    monkeypatch.setattr(database, "engine", engine)
    await database.init_db()
    await database.init_db()

    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {column["name"] for column in inspect(sync_conn).get_columns("nodes")}
        )

    assert {
        "check_interval",
        "check_interval_unit",
        "last_notified_status",
        "last_alert_time",
        "blocked",
        "blocked_checked_at",
        "last_latency_ms",
        "last_error",
        "consecutive_failures",
        "check_history",
    } <= columns
    await engine.dispose()
