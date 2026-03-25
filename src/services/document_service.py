from uuid import UUID
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Document, Page, Chunk
from src.db.repositories import DocumentRepository, PageRepository, ChunkRepository
from src.services.parser_service import ParserService
from src.services.embedding_service import EmbeddingService
from src.services.elasticsearch_service import es_service
from src.core.logging import get_logger

logger = get_logger(__name__)

class DocumentService:
    """Сервіс для комплексного керування документами (Парсинг -> Сторінки -> Чанки -> Вектори)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.page_repo = PageRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.parser = ParserService()
        self.embedding_service = EmbeddingService()

    async def add_file(self, file_path: Path, title: Optional[str] = None) -> Document:
        """
        Додає файл у систему. Керує транзакцією БД та індексацією в ES.
        """
        if title is None:
            title = file_path.stem

        logger.info(f"Початок додавання документа: '{title}' ({file_path})")

        # 1. Парсимо на сторінки (поза транзакцією, бо це повільно)
        try:
            pages_dict = self.parser.parse_pages(file_path)
        except Exception as e:
            logger.error(f"Помилка при парсингу файлу '{file_path}': {e}")
            raise

        if not pages_dict or all(not content.strip() for content in pages_dict.values()):
            logger.error(f"Документ '{title}' не містить тексту після парсингу")
            raise ValueError(f"Документ '{title}' порожній")

        logger.info(f"Документ '{title}' розпарсено на {len(pages_dict)} сторінок")

        # 2. Виконуємо основну логіку в транзакції
        # Якщо транзакція вже розпочата (наприклад, у тестах), використовуємо її
        if self.session.in_transaction():
            doc, all_pages, total_chunks = await self._add_file_logic(pages_dict, title, file_path)
        else:
            async with self.session.begin():
                doc, all_pages, total_chunks = await self._add_file_logic(pages_dict, title, file_path)

        # 3. Індексуємо сторінки в Elasticsearch (поза транзакцією БД)
        try:
            await es_service.index_pages(all_pages, doc.title)
            logger.info(f"[{doc.id}] Документ успішно проіндексовано в ES")
        except Exception as e:
            logger.error(f"[{doc.id}] Помилка індексації в Elasticsearch: {e}")
            
        logger.info(f"[{doc.id}] Документ '{title}' успішно додано. Всього чанків: {total_chunks}")
        return doc

    async def _add_file_logic(self, pages_dict: dict, title: str, file_path: Path) -> tuple[Document, list[Page], int]:
        """Внутрішня логіка додавання документа (має бути всередині транзакції)."""
        # 1. Перевірка на дублікати за назвою
        existing_doc = await self.doc_repo.get_by_title(title)
        if existing_doc:
            logger.error(f"Документ з назвою '{title}' вже існує (ID: {existing_doc.id})")
            raise ValueError(f"Документ з назвою '{title}' вже існує")

        # 2. Створюємо документ
        doc = Document(
            title=title,
            source_file=str(file_path),
            doc_type=file_path.suffix.upper().replace(".", "")
        )
        await self.doc_repo.create(doc)
        doc_id = doc.id
        logger.info(f"[{doc_id}] Створено запис документа")

        all_pages = []
        total_chunks = 0
        MAX_CHUNKS = 1000

        for page_num, content in pages_dict.items():
            if not content.strip():
                continue

            # 3. Створюємо сторінку
            page = Page(
                document_id=doc_id,
                page_number=page_num,
                content=content
            )
            await self.page_repo.create(page)
            all_pages.append(page)
            logger.debug(f"[{doc_id}] Створено сторінку {page_num}")

            # 4. Чанкуємо текст сторінки
            chunk_texts = await self.parser.chunk_text(content)
            if not chunk_texts:
                continue

            # Перевірка на ліміт чанків
            if total_chunks + len(chunk_texts) > MAX_CHUNKS:
                logger.error(f"[{doc_id}] Перевищено ліміт чанків ({MAX_CHUNKS}). Поточна кількість: {total_chunks + len(chunk_texts)}")
                raise ValueError(f"Документ занадто великий (перевищено ліміт у {MAX_CHUNKS} чанків)")

            # 5. Генеруємо вектори
            try:
                embeddings = await self.embedding_service.get_embeddings(chunk_texts)
            except Exception as e:
                logger.error(f"[{doc_id}] Помилка генерації векторів для сторінки {page_num}: {e}")
                raise

            # 6. Формуємо чанки
            db_chunks = []
            for i, (text, vector) in enumerate(zip(chunk_texts, embeddings)):
                if vector is None:
                    continue
                db_chunks.append(Chunk(
                    page_id=page.id,
                    content=text,
                    embedding=vector,
                    chunk_index=i
                ))

            if db_chunks:
                await self.chunk_repo.create_bulk(db_chunks)
                total_chunks += len(db_chunks)
            
            logger.debug(f"[{doc_id}] Збережено {len(db_chunks)} чанків для сторінки {page_num}")
        
        return doc, all_pages, total_chunks

    async def get_document(self, doc_id: UUID) -> Optional[Document]:
        """Отримує документ за його ID."""
        return await self.doc_repo.get_by_id(doc_id)

    async def get_all_documents(self, skip: int = 0, limit: int = 100) -> list[Document]:
        """Отримує список документів з пагінацією."""
        return await self.doc_repo.get_all(skip=skip, limit=limit)

    async def clear_all_documents(self):
        """Повністю очищає БД та індекс Elasticsearch."""
        logger.info("Початок повного очищення документів...")
        try:
            # Очищення БД (каскадне видалення)
            if self.session.in_transaction():
                await self.doc_repo.clear_all()
            else:
                async with self.session.begin():
                    await self.doc_repo.clear_all()
            
            # Очищення Elasticsearch
            await es_service.clear_index()
            
            logger.info("Всі документи успішно видалені з БД та ES")
        except Exception as e:
            logger.error(f"Помилка при очищенні документів: {e}", exc_info=True)
            raise

    async def reindex_all(self, docs_dir: Path = Path("documents")) -> dict:
        """Очищає все та переіндексує файли з вказаної директорії."""
        await self.clear_all_documents()
        
        if not docs_dir.exists():
            logger.warning(f"Директорія {docs_dir} не існує")
            return {"processed": 0, "errors": 0}

        supported_extensions = {".pdf", ".txt", ".docx", ".html"}
        processed = 0
        errors = 0
        
        logger.info(f"Початок переіндексації з {docs_dir}...")
        
        for file_path in docs_dir.iterdir():
            if file_path.suffix.lower() in supported_extensions:
                try:
                    # add_file має свою транзакцію
                    await self.add_file(file_path, title=file_path.stem)
                    processed += 1
                    logger.info(f"[{processed}] Проіндексовано: {file_path.name}")
                except Exception as e:
                    errors += 1
                    logger.error(f"Помилка при індексації {file_path.name}: {e}")
                    
        logger.info(f"Переіндексація завершена. Оброблено: {processed}, помилок: {errors}")
        return {"processed": processed, "errors": errors}

    async def delete_document(self, doc_id: UUID) -> bool:
        """
        Видаляє документ та всі пов'язані з ним дані (сторінки, чанки) з БД та ES.
        """
        logger.info(f"Початок видалення документа: {doc_id}")
        
        success = await self.doc_repo.delete_by_id(doc_id)
        if not success:
            logger.warning(f"Документ {doc_id} не знайдено для видалення")
            return False
        
        await self.session.flush()

        # Видаляємо з Elasticsearch (навіть якщо транзакція БД вже закрита)
        try:
            await es_service.delete_by_document_id(doc_id)
        except Exception as e:
            logger.error(f"Помилка при видаленні документа {doc_id} з ES: {e}")

        logger.info(f"Документ {doc_id} успішно видалено")
        return True
