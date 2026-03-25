from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PageBase(BaseModel):
    """Базова схема сторінки документа."""

    page_number: int = Field(..., description="Порядковий номер сторінки")
    content: str = Field(..., description="Текст сторінки")
    meta_data: dict | None = Field(default=None, description="Додаткові метадані сторінки")


class PageCreate(PageBase):
    """Схема для створення сторінки."""

    document_id: UUID


class PageUpdate(BaseModel):
    """Схема для оновлення сторінки."""

    page_number: int | None = None
    content: str | None = None
    meta_data: dict | None = None


class PageResponse(PageBase):
    """Схема сторінки для відповідей API."""

    id: UUID
    document_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
