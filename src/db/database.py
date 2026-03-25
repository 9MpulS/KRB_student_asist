from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings
from src.core.logging import get_logger
from src.db.models import Base

logger = get_logger(__name__)

# Async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Ініціалізація бази даних: створення розширень та таблиць."""
    try:
        async with engine.begin() as conn:
            # Створення розширення pgvector, якщо воно ще не створене
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Створення всіх таблиць
            # run_sync дозволяє викликати синхронний metadata.create_all
            await conn.run_sync(Base.metadata.create_all)

        logger.info("База даних успішно ініціалізована (таблиці та розширення створено)")
    except Exception as e:
        logger.error(f"Помилка при ініціалізації бази даних: {e}", exc_info=True)
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для отримання async database session.

    Yields:
        AsyncSession: Database session

    Raises:
        Exception: При помилках роботи з БД
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Перевірка працездатності підключення до БД."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
