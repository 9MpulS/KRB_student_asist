import uuid
import logging
from typing import List, Optional, Generic, TypeVar, Type
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Base, Document, Page, Chunk

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    """Базовий асинхронний репозиторій."""
    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: uuid.UUID) -> Optional[T]:
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def create(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def delete_by_id(self, id: uuid.UUID) -> bool:
        # Спочатку отримуємо об'єкт для перевірки існування та можливості видалення
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            return True
        return False

class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: AsyncSession):
        super().__init__(Document, session)

    async def get_by_title(self, title: str) -> Optional[Document]:
        result = await self.session.execute(select(Document).where(Document.title == title))
        return result.scalar_one_or_none()

    async def clear_all(self):
        """Видаляє всі документи з бази даних (каскадно)."""
        await self.session.execute(delete(Document))
        await self.session.flush()

class PageRepository(BaseRepository[Page]):
    def __init__(self, session: AsyncSession):
        super().__init__(Page, session)

    async def create_bulk(self, pages: List[Page]) -> List[Page]:
        self.session.add_all(pages)
        await self.session.flush()
        return pages

    async def get_all_pages_for_migration(self) -> List[Page]:
        """
        Отримує всі сторінки з бази даних для міграції в Elasticsearch.
        
        Returns:
            Список всіх сторінок з підвантаженими документами.
        """
        try:
            stmt = (
                select(Page)
                .options(
                    selectinload(Page.document)
                )
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().unique().all())
            
        except Exception as e:
            logger.error(f"Error while fetching all pages for migration: {e}", exc_info=True)
            return []
    
    async def get_pages_by_ids(self, page_ids: List[uuid.UUID]) -> List[Page]:
        """
        Отримує сторінки за списком ID.
        
        Args:
            page_ids: Список UUID сторінок.
            
        Returns:
            Список сторінок з підвантаженими документами, відсортованих за порядком в page_ids.
        """
        if not page_ids:
            return []
            
        try:
            stmt = (
                select(Page)
                .options(
                    selectinload(Page.document)
                )
                .where(Page.id.in_(page_ids))
            )
            
            result = await self.session.execute(stmt)
            pages = list(result.scalars().unique().all())
            
            # Сортуємо за порядком в page_ids (зберігаємо релевантність з ES)
            page_dict = {page.id: page for page in pages}
            sorted_pages = [page_dict[pid] for pid in page_ids if pid in page_dict]
            
            return sorted_pages
            
        except Exception as e:
            logger.error(f"Error while getting pages by ids: {e}", exc_info=True)
            return []

class ChunkRepository(BaseRepository[Chunk]):
    def __init__(self, session: AsyncSession):
        super().__init__(Chunk, session)

    async def create_bulk(self, chunks: List[Chunk]) -> List[Chunk]:
        self.session.add_all(chunks)
        await self.session.flush()
        return chunks

    async def search_similar(self, embedding: list[float], limit: int = 5) -> list[Chunk]:
        """
        Виконує векторний пошук схожих чанків з використанням pgvector.
        
        Args:
            embedding: Вектор для пошуку (list[float]).
            limit: Максимальна кількість результатів.
            
        Returns:
            Список чанків, відсортованих за схожістю, з підвантаженими сторінками та документами.
        """
        try:
            # Використовуємо cosine_distance для pgvector (<=>)
            # selectinload використовується для ефективного та передбачуваного завантаження зв'язків
            query = (
                select(Chunk)
                .options(
                    selectinload(Chunk.page).selectinload(Page.document)
                )
                .order_by(Chunk.embedding.cosine_distance(embedding))
                .limit(limit)
            )
            
            result = await self.session.execute(query)
            # .unique() необхідний при використанні joinedload/selectinload з певними типами сесій
            return list(result.scalars().unique().all())
            
        except Exception as e:
            logger.error(f"Error during vector search: {e}", exc_info=True)
            return []

    async def search_text(self, query: str, limit: int = 5) -> list[Chunk]:
        """
        Виконує повнотекстовий пошук за ключовими словами (PostgreSQL FTS).
        
        Args:
            query: Текстовий запит для пошуку.
            limit: Максимальна кількість результатів.
            
        Returns:
            Список чанків, відсортованих за релевантністю (ts_rank).
        """
        try:
            from sqlalchemy import func
            
            # Створюємо tsvector та tsquery для української/простої обробки
            tsvector = func.to_tsvector('simple', func.lower(Chunk.content))
            # Використовуємо websearch_to_tsquery для підтримки операторів OR, AND, кавичок
            tsquery = func.websearch_to_tsquery('simple', func.lower(query))
            
            stmt = (
                select(Chunk)
                .options(
                    selectinload(Chunk.page).selectinload(Page.document)
                )
                .where(tsvector.op('@@')(tsquery))
                .order_by(func.ts_rank(tsvector, tsquery).desc())
                .limit(limit)
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().unique().all())
            
        except Exception as e:
            logger.error(f"Error during full-text search: {e}", exc_info=True)
            return []

    async def get_chunks_by_ids(self, ids: List[uuid.UUID]) -> List[Chunk]:
        """
        Отримує чанки за списком ID зі збереженням порядку.
        
        Args:
            ids: Список UUID чанків.
            
        Returns:
            Список чанків з підвантаженими сторінками та документами у тому ж порядку, що і vхідні ID.
        """
        if not ids:
            return []
            
        try:
            from sqlalchemy import func
            
            # Конвертуємо UUID в стрінги для pg_array_position (або залишаємо як є, якщо БД підтримує)
            # В PostgreSQL array_position(anyarray, anyelement)
            
            stmt = (
                select(Chunk)
                .options(
                    selectinload(Chunk.page).selectinload(Page.document)
                )
                .where(Chunk.id.in_(ids))
                .order_by(func.array_position(ids, Chunk.id))
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().unique().all())
            
        except Exception as e:
            logger.error(f"Error while getting chunks by ids: {e}", exc_info=True)
            return []

    async def get_chunks_by_page_ids(self, page_ids: List[uuid.UUID]) -> List[Chunk]:
        """
        Отримує всі чанки для заданих сторінок.
        
        Args:
            page_ids: Список UUID сторінок.
            
        Returns:
            Список чанків з підвантаженими сторінками та документами.
        """
        if not page_ids:
            return []
            
        try:
            stmt = (
                select(Chunk)
                .options(
                    selectinload(Chunk.page).selectinload(Page.document)
                )
                .where(Chunk.page_id.in_(page_ids))
                .order_by(Chunk.page_id, Chunk.chunk_index)
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().unique().all())
            
        except Exception as e:
            logger.error(f"Error while getting chunks by page ids: {e}", exc_info=True)
            return []

    async def get_all_chunks_for_migration(self) -> List[Chunk]:
        """
        Отримує всі чанки з бази даних для міграції в Elasticsearch.
        
        Returns:
            Список всіх чанків з підвантаженими сторінками та документами.
        """
        try:
            stmt = (
                select(Chunk)
                .options(
                    selectinload(Chunk.page).selectinload(Page.document)
                )
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().unique().all())
            
        except Exception as e:
            logger.error(f"Error while fetching all chunks for migration: {e}", exc_info=True)
            return []
