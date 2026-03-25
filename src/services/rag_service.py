import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import get_logger
from src.db.models import Chunk, Page
from src.db.repositories import ChunkRepository, PageRepository
from src.schemas.question import QuestionResponse
from src.services.elasticsearch_service import es_service
from src.services.embedding_service import EmbeddingService
from src.services.llm_service import LLMService

logger = get_logger(__name__)


class RAGService:
    """Сервіс для реалізації RAG (Retrieval-Augmented Generation) пайплайну."""

    def __init__(self, session: AsyncSession):
        """
        Ініціалізація сервісу.

        Args:
            session: Асинхронна сесія бази даних.
        """
        self.session = session
        self.chunk_repo = ChunkRepository(session)
        self.page_repo = PageRepository(session)
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()
        logger.info("RAGService ініціалізовано")

    async def _get_relevant_chunks_vec(self, question_embedding: list[float], limit: int = 5) -> list[Chunk]:
        """
        Знаходить найбільш релевантні фрагменти тексту для заданого вектора питання (Векторний пошук).

        Args:
            question_embedding: Векторне представлення питання.
            limit: Кількість чанків для повернення.

        Returns:
            List[Chunk]: Список знайдених чанків з підвантаженим контекстом.
        """
        try:
            logger.info(f"Векторний пошук {limit} релевантних чанків")

            chunks = await self.chunk_repo.search_similar(embedding=question_embedding, limit=limit)

            logger.info(f"Векторний пошук: знайдено {len(chunks)} чанків")
            return chunks
        except Exception as e:
            logger.error(f"Помилка при векторному пошуку: {e}", exc_info=True)
            return []

    async def _get_relevant_chunks_fts(self, query: str, limit: int = 5) -> list[Chunk]:
        """
        Знаходить релевантні фрагменти тексту за допомогою повнотекстового пошуку (FTS).

        Args:
            query: Текстовий запит.
            limit: Кількість чанків для повернення.

        Returns:
            List[Chunk]: Список знайдених чанків з підвантаженим контекстом.
        """
        try:
            logger.info(f"FTS пошук {limit} релевантних чанків за запитом: '{query}'")

            chunks = await self.chunk_repo.search_text(query=query, limit=limit)

            logger.info(f"FTS пошук: знайдено {len(chunks)} чанків")
            return chunks
        except Exception as e:
            logger.error(f"Помилка при FTS пошуку: {e}", exc_info=True)
            return []

    async def _get_relevant_pages_es(self, query: str, limit: int | None = None) -> list[Page]:
        """
        Знаходить релевантні сторінки за допомогою Elasticsearch.
        """
        if limit is None:
            limit = settings.RETRIEVAL_LIMIT_ES

        try:
            logger.info(f"Elasticsearch пошук {limit} релевантних сторінок за запитом: '{query}'")

            # 1. Отримуємо ID сторінок з ES
            page_ids = await es_service.search(query=query, limit=limit)

            if not page_ids:
                logger.info("Elasticsearch не знайшов жодного результату")
                return []

            # 2. Отримуємо сторінки за ID
            pages = await self.page_repo.get_pages_by_ids(page_ids)

            logger.info(f"Elasticsearch пошук: знайдено {len(pages)} сторінок")
            return pages
        except Exception as e:
            logger.error(f"Помилка при пошуку через Elasticsearch: {e}", exc_info=True)
            return []

    async def retrieve_chunks(self, question: str) -> list[Chunk]:
        """
        Метод пошуку релевантних фрагментів тексту.
        Використовує гібридний підхід: Векторний пошук + Повнотекстовий пошук (згенерований LLM).

        Args:
            question: Запит користувача.

        Returns:
            List[Chunk]: Список унікальних релевантних чанків.
        """
        ret_start = time.perf_counter()
        logger.info(f"Початок пошуку для запиту: '{question}'")

        # 1. Генерація FTS запиту та Embeddings (паралельно)
        logger.info("Генерація FTS-запиту та векторного представлення...")
        fts_query_task = asyncio.create_task(self.llm_service.generate_fts_query(question))
        embedding_task = asyncio.create_task(self.embedding_service.get_embeddings(question))

        fts_query, question_embedding = await asyncio.gather(fts_query_task, embedding_task)

        # 2. Виконання пошуків (послідовно, щоб уникнути конфліктів у сесії БД)
        logger.info(f"Виконання гібридного пошуку (FTS: '{fts_query}')")

        vec_chunks = await self._get_relevant_chunks_vec(question_embedding, limit=settings.RETRIEVAL_LIMIT_VEC)  # type: ignore
        fts_chunks = await self._get_relevant_chunks_fts(fts_query, limit=settings.RETRIEVAL_LIMIT_FTS)

        # 3. Об'єднання та дедублікація за ID
        seen_ids = set()
        unique_chunks = []

        # Пріоритет векторному пошуку
        for chunk in vec_chunks + fts_chunks:
            if chunk.id not in seen_ids:
                unique_chunks.append(chunk)
                seen_ids.add(chunk.id)

        ret_time = time.perf_counter() - ret_start
        logger.info(f"Пошук завершено за {ret_time:.2f}s. Знайдено унікальних чанків: {len(unique_chunks)}")
        return unique_chunks

    async def ask_question(self, question: str) -> QuestionResponse:
        """
        Основний метод RAG-пайплайну для отримання відповіді на питання.
        """
        start_time = time.perf_counter()
        logger.info(f"Отримано нове питання: '{question}'")

        # 1. Пошук (Retrieval)
        retrieved_chunks = await self.retrieve_chunks(question)

        if not retrieved_chunks:
            logger.info("Релевантних фрагментів не знайдено.")
            return QuestionResponse(
                answer=(
                    "На жаль, я не знайшов достатньо інформації у базі знань, "
                    "щоб впевнено відповісти на ваше запитання. Спробуйте уточнити запит."
                ),
                sources=[],
                context=None,
            )

        # 1.1. Ранжування (Reranking)
        # Ранжуємо отримані чанки за допомогою LLM
        rerank_start = time.perf_counter()
        chunks = await self.llm_service.rerank_chunks(question, retrieved_chunks)

        # Ранкер сам відфільтрував результати (Score >= 0.8) та обмежив їх кількість (Max 3)
        rerank_time = time.perf_counter() - rerank_start
        logger.info(f"Ранжування завершено за {rerank_time:.2f}s. Вибрано {len(chunks)} найкращих чанків.")

        # 2. Підготовка контексту
        context_start = time.perf_counter()
        context = "\n\n".join([chunk.content for chunk in chunks])

        # 3. Збір унікальних джерел
        sources_set = set()
        for chunk in chunks:
            if chunk.page and chunk.page.document:
                doc = chunk.page.document
                source = f"{doc.title} (стор. {chunk.page.page_number})"
                if doc.source_url:
                    source += f" - {doc.source_url}"
                sources_set.add(source)

        sources = sorted(list(sources_set))
        context_time = time.perf_counter() - context_start
        logger.debug(f"Підготовка контексту та джерел: {context_time:.2f}s")

        # 4. Генерація відповіді (Generation)
        gen_start = time.perf_counter()
        try:
            answer = await self.llm_service.generate_answer(question, context)
        except Exception as e:
            logger.error(f"Помилка при генерації відповіді: {e}")
            raise
        gen_time = time.perf_counter() - gen_start
        logger.info(f"Генерація відповіді LLM: {gen_time:.2f}s")

        total_time = time.perf_counter() - start_time
        logger.info(f"Пайплайн завершено за {total_time:.2f}s")

        return QuestionResponse(answer=answer, sources=sources, context=context if settings.DEBUG else None)
