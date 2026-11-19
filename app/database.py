from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.DB_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def migrate(sync_conn):
            columns = {column["name"] for column in inspect(sync_conn).get_columns("nodes")}
            additions = {
                "check_interval": "ALTER TABLE nodes ADD COLUMN check_interval INTEGER DEFAULT 1",
                "check_interval_unit": "ALTER TABLE nodes ADD COLUMN check_interval_unit VARCHAR DEFAULT 'm'",
                "last_notified_status": "ALTER TABLE nodes ADD COLUMN last_notified_status BOOLEAN",
                "blocked": "ALTER TABLE nodes ADD COLUMN blocked BOOLEAN",
                "blocked_checked_at": "ALTER TABLE nodes ADD COLUMN blocked_checked_at DATETIME",
            }
            for name, statement in additions.items():
                if name not in columns:
                    sync_conn.exec_driver_sql(statement)

        await conn.run_sync(migrate)
