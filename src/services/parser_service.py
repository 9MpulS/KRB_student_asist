from pathlib import Path

from chonkie import TokenChunker
from markitdown import MarkItDown

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class ParserService:
    """Сервіс для парсингу документів та розбиття на чанки."""

    def __init__(self):
        """Ініціалізація MarkItDown."""
        self._md = MarkItDown()
        logger.info("ParserService ініціалізовано з MarkItDown")

    def parse_file(self, file_path: Path) -> str:
        """Конвертує файл у Markdown текст."""
        try:
            logger.info(f"Початок парсингу файлу: {file_path}")
            result = self._md.convert(str(file_path))
            logger.info(f"Файл успішно розпарсено: {file_path}")
            return result.text_content
        except Exception as e:
            logger.error(f"Помилка при парсингу {file_path}: {e}")
            raise

    def parse_pages(self, file_path: Path) -> dict[int, str]:
        """Конвертує файл і розбиває його на сторінки."""
        try:
            full_text = self.parse_file(file_path)

            if "\f" in full_text:
                pages_list = full_text.split("\f")
                pages_dict = {i + 1: page.strip() for i, page in enumerate(pages_list) if page.strip()}
                logger.info(f"Файл розділено на {len(pages_dict)} сторінок за допомогою \\f")
                return pages_dict

            logger.info("Маркерів сторінок не знайдено, повертаємо весь текст як одну сторінку")
            return {1: full_text.strip()}

        except Exception as e:
            logger.error(f"Помилка при розбитті на сторінки {file_path}: {e}")
            raise

    async def chunk_text(self, text: str, chunk_size: int | None = None, chunk_overlap: int | None = None) -> list[str]:
        """Розбиває текст на чанки за допомогою Chonkie."""
        if not text.strip():
            return []

        size = chunk_size or settings.CHUNK_SIZE
        overlap = chunk_overlap or settings.CHUNK_OVERLAP

        try:
            logger.debug(f"Розбиття тексту на чанки (size={size}, overlap={overlap})")
            # Ініціалізація чанкера згідно з налаштуваннями
            chunker = TokenChunker(tokenizer="character", chunk_size=size, chunk_overlap=overlap)
            chunks = chunker.chunk(text)
            return [chunk.text for chunk in chunks]
        except Exception as e:
            logger.error(f"Помилка при чанкуванні тексту: {e}")
            return []
