import time

import ollama

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Сервіс для генерації векторних представлень (embeddings) за допомогою Ollama."""

    def __init__(self):
        """Ініціалізація асинхронного клієнта Ollama."""
        self.client = ollama.AsyncClient(host=settings.OLLAMA_HOST, timeout=settings.AI_TIMEOUT)
        self.model = settings.EMBEDDING_MODEL
        logger.info(f"EmbeddingService ініціалізовано з моделлю: {self.model} (timeout: {settings.AI_TIMEOUT}s)")

    async def get_embeddings(self, input_data: str | list[str]) -> list[float] | list[list[float]]:
        """
        Генерує вектори для тексту або списку текстів.

        Args:
            input_data: Текст або список текстових фрагментів.

        Returns:
            list[float] | list[list[float]]: Вектор або список векторів.
        """
        if not input_data:
            return []

        is_single = isinstance(input_data, str)
        texts = [input_data] if is_single else input_data

        try:
            logger.info(f"Генерація embeddings для {len(texts)} фрагментів за допомогою {self.model}")

            # Ollama API .embed підтримує список рядків в 'input',
            # але ми обробляємо по одному або в циклі згідно з прикладом завдання
            # для більшої гнучкості або сумісності (залежить від версії бібліотеки)
            embeddings = []
            for text in texts:
                start_time = time.perf_counter()
                response = await self.client.embed(model=self.model, input=text)
                duration = time.perf_counter() - start_time
                logger.debug(f"Ollama embedding request took {duration:.2f}s")
                embeddings.append(response["embeddings"][0])

            logger.info(f"Успішно згенеровано {len(embeddings)} векторів")
            return embeddings[0] if is_single else embeddings
        except Exception as e:
            logger.error(f"Помилка при запиті до Ollama для моделі {self.model}: {e}")
            raise

    async def close(self):
        """Закриває клієнт Ollama (якщо підтримується)."""
        # У поточних версіях ollama-python AsyncClient не має методу close()
        # або він не є обов'язковим для явного виклику.
        logger.debug("EmbeddingService.close() called (no action needed for current ollama client)")
