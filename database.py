"""
database.py — SQLAlchemy async (SQLite через aiosqlite).
Без PostgreSQL, без asyncpg — просто файл trading_bot.db у папці проекту.
"""

from __future__ import annotations

from decimal import Decimal
from typing import AsyncGenerator

from sqlalchemy import BigInteger, Numeric, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DATABASE_URL


# ──────────────────────────────────────────────
# Base & Model
# ──────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    exchange_risk_1: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("2"))
    exchange_risk_2: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("2.5"))
    prop_balance:    Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("1000"))
    prop_risk_1:     Mapped[Decimal] = mapped_column(Numeric(5,  2), nullable=False, default=Decimal("0.5"))
    prop_risk_2:     Mapped[Decimal] = mapped_column(Numeric(5,  2), nullable=False, default=Decimal("1"))

    def __repr__(self) -> str:
        return (
            f"UserSettings(user_id={self.user_id}, "
            f"ex_r1={self.exchange_risk_1}, ex_r2={self.exchange_risk_2}, "
            f"prop_bal={self.prop_balance}, p_r1={self.prop_risk_1}, p_r2={self.prop_risk_2})"
        )


# ──────────────────────────────────────────────
# Database — engine + session factory
# ──────────────────────────────────────────────

class Database:
    def __init__(self, url: str) -> None:
        # SQLite не підтримує pool_size/max_overflow — використовуємо StaticPool
        connect_args = {}
        kwargs = {}
        if url.startswith("sqlite"):
            from sqlalchemy.pool import StaticPool
            connect_args = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool

        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=False,
            connect_args=connect_args,
            **kwargs,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    def get_session(self) -> AsyncSession:
        return self._session_factory()

    async def session_context(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_tables(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def ping(self) -> bool:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def dispose(self) -> None:
        await self.engine.dispose()


# ──────────────────────────────────────────────
# Repository
# ──────────────────────────────────────────────

class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: int) -> UserSettings:
        settings = await self._session.get(UserSettings, user_id)
        if settings is None:
            settings = UserSettings(user_id=user_id)
            self._session.add(settings)
            await self._session.flush()
        return settings

    async def update_field(self, user_id: int, field: str, value: Decimal) -> UserSettings:
        allowed = {"exchange_risk_1", "exchange_risk_2", "prop_balance", "prop_risk_1", "prop_risk_2"}
        if field not in allowed:
            raise ValueError(f"Unknown field: {field!r}")
        settings = await self.get_or_create(user_id)
        setattr(settings, field, value)
        await self._session.flush()
        return settings


# ──────────────────────────────────────────────
# Глобальний екземпляр
# ──────────────────────────────────────────────

db = Database(DATABASE_URL)


async def init_db() -> None:
    alive = await db.ping()
    if not alive:
        raise RuntimeError("Cannot connect to database. Check DATABASE_URL in .env")
    await db.create_tables()
