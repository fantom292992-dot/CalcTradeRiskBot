"""
db_middleware.py — aiogram BaseMiddleware для SQLAlchemy.

Що робить:
  - Відкриває AsyncSession на початку кожного апдейту
  - Кладе session і repo в data[] — звідти хендлери беруть їх як аргументи
  - Після хендлера: commit якщо успішно, rollback якщо виняток
  - Закриває сесію в будь-якому разі (finally)

Використання в handlers.py:
    async def my_handler(message: Message, session: AsyncSession, repo: UserRepo):
        settings = await repo.get_or_create(message.from_user.id)
"""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from database import Database, UserRepo


class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware передає session і repo у кожен хендлер через data dict.
    """

    def __init__(self, database: Database) -> None:
        self._db = database
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._db.get_session() as session:
            # Робимо session та repo доступними як параметри хендлерів
            data["session"] = session
            data["repo"] = UserRepo(session)

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
