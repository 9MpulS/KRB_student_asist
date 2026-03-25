import logging
import uuid
from typing import List, Optional
from elasticsearch import AsyncElasticsearch, helpers
from src.core.config import settings

logger = logging.getLogger(__name__)

class ElasticsearchService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ElasticsearchService, cls).__new__(cls)
            cls._instance._client = None
        return cls._instance

    def __init__(self):
        # Initialization logic only runs once due to the singleton pattern check
        if self._client is None:
            try:
                self._client = AsyncElasticsearch(
                    hosts=[settings.ELASTICSEARCH_URL]
                )
                logger.info(f"Elasticsearch client initialized with URL: {settings.ELASTICSEARCH_URL}")
            except Exception as e:
                logger.error(f"Failed to initialize Elasticsearch client: {e}")
                raise

    @property
    def client(self) -> AsyncElasticsearch:
        return self._client

    async def create_index(self, index_name: Optional[str] = None):
        """Створює індекс з маппінгом, якщо він не існує."""
        if index_name is None:
            index_name = settings.ES_INDEX_NAME

        if await self._client.indices.exists(index=index_name):
            logger.debug(f"Index {index_name} already exists")
            return

        mapping = {
            "mappings": {
                "properties": {
                    "page_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "page_number": {"type": "integer"},
                    "content": {"type": "text", "analyzer": "ukrainian"},
                    "document_title": {"type": "keyword"}
                }
            }
        }

        try:
            await self._client.indices.create(index=index_name, body=mapping)
            logger.info(f"Created index {index_name} with mapping")
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            raise

    async def index_pages(self, pages: List, doc_title: str):
        """Пакетна індексація сторінок."""
        if not pages:
            return

        await self.create_index()

        actions = [
            {
                "_index": settings.ES_INDEX_NAME,
                "_id": str(page.id),
                "page_id": str(page.id),
                "document_id": str(page.document_id),
                "page_number": page.page_number,
                "content": page.content,
                "document_title": doc_title
            }
            for page in pages
        ]

        try:
            success, failed = await helpers.async_bulk(self._client, actions)
            logger.info(f"Successfully indexed {success} pages to Elasticsearch. Failed: {len(failed) if isinstance(failed, list) else failed}")
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            raise

    async def search(self, query: str, limit: int = 5) -> List[uuid.UUID]:
        """Виконує повнотекстовий пошук в Elasticsearch (тільки по контенту сторінок)."""
        search_query = {
            "query": {
                "match": {
                    "content": query
                }
            },
            "size": limit
        }

        try:
            response = await self._client.search(
                index=settings.ES_INDEX_NAME,
                body=search_query
            )
            
            ids = []
            for hit in response["hits"]["hits"]:
                try:
                    ids.append(uuid.UUID(hit["_id"]))
                except (ValueError, KeyError):
                    logger.warning(f"Invalid UUID in ES hit: {hit['_id']}")
            
            logger.info(f"ES search for '{query}' returned {len(ids)} results")
            return ids
        except Exception as e:
            logger.error(f"ES search failed: {e}")
            return []

    async def delete_by_document_id(self, doc_id: uuid.UUID):
        """Видаляє всі сторінки документа з Elasticsearch."""
        query = {
            "query": {
                "term": {
                    "document_id": str(doc_id)
                }
            }
        }
        try:
            response = await self._client.delete_by_query(
                index=settings.ES_INDEX_NAME,
                body=query,
                refresh=True
            )
            logger.info(f"Deleted {response.get('deleted', 0)} pages for document {doc_id} from Elasticsearch")
        except Exception as e:
            logger.error(f"Failed to delete pages for document {doc_id} from ES: {e}")
            # Не перериваємо основний процес, якщо ES повернув помилку
            pass

    async def clear_index(self, index_name: Optional[str] = None):
        """Видаляє всі документи з індексу Elasticsearch."""
        if index_name is None:
            index_name = settings.ES_INDEX_NAME
        
        if not await self._client.indices.exists(index=index_name):
            return

        query = {"query": {"match_all": {}}}
        try:
            await self._client.delete_by_query(
                index=index_name,
                body=query,
                refresh=True
            )
            logger.info(f"Cleared all documents from ES index {index_name}")
        except Exception as e:
            logger.error(f"Failed to clear ES index {index_name}: {e}")
            raise

    async def close(self):
        if self._client:
            await self._client.close()
            logger.info("Elasticsearch client closed")

# Singleton instance
es_service = ElasticsearchService()
