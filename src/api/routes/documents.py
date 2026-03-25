import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from src.api.dependencies import get_document_service
from src.core.logging import get_logger
from src.schemas.document import DocumentResponse
from src.services.document_service import DocumentService

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    service: DocumentService = Depends(get_document_service),
):
    """Отримати список документів з пагінацією."""
    return await service.get_all_documents(skip=skip, limit=limit)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: UUID, service: DocumentService = Depends(get_document_service)):
    """Отримати деталі документа за ID."""
    doc = await service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: UUID, service: DocumentService = Depends(get_document_service)):
    """Видалити документ та всі пов'язані дані."""
    success = await service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return None


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), service: DocumentService = Depends(get_document_service)):
    """Завантажити та обробити новий документ."""
    logger.info(f"Отримано запит на завантаження файлу: {file.filename}")

    # Створюємо тимчасовий файл для обробки
    suffix = Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        doc = await service.add_file(tmp_path, title=Path(file.filename or "").stem)
        return doc
    except ValueError as e:
        logger.warning(f"Помилка валідації при завантаженні: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Критична помилка при завантаженні: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing document")
    finally:
        # Видаляємо тимчасовий файл
        if tmp_path.exists():
            tmp_path.unlink()


@router.post("/reindex", status_code=status.HTTP_200_OK)
async def reindex_documents(service: DocumentService = Depends(get_document_service)):
    """Повністю очистити БД та ES та переіндексувати файли з папки documents."""
    logger.info("Отримано запит на повну переіндексацію")
    result = await service.reindex_all()
    return result
