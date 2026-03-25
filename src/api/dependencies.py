from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_db
from src.services.document_service import DocumentService
from src.services.rag_service import RAGService


async def get_document_service(session: AsyncSession = Depends(get_db)) -> DocumentService:
    """
    Dependency для отримання екземпляра DocumentService з ін'єкцією сесії БД.
    """
    return DocumentService(session)


async def get_rag_service(session: AsyncSession = Depends(get_db)) -> RAGService:
    """
    Dependency для отримання екземпляра RAGService з ін'єкцією сесії БД.
    """
    return RAGService(session)
