from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class PageBase(BaseModel):
    """Базова схема сторінки документа."""
    page_number: int = Field(..., description="Порядковий номер сторінки")
    content: str = Field(..., description="Текст сторінки")
    meta_data: Optional[dict] = Field(default=None, description="Додаткові метадані сторінки")

class PageCreate(PageBase):
    """Схема для створення сторінки."""
    document_id: UUID

class PageUpdate(BaseModel):
    """Схема для оновлення сторінки."""
    page_number: Optional[int] = None
    content: Optional[str] = None
    meta_data: Optional[dict] = None

class PageResponse(PageBase):
    """Схема сторінки для відповідей API."""
    id: UUID
    document_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
