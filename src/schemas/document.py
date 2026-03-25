from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    """Базова схема документа."""

    title: str = Field(..., min_length=1, max_length=255, description="Заголовок документа")
    source_url: str | None = Field(None, max_length=512, description="URL джерела")
    source_file: str | None = Field(None, max_length=255, description="Шлях до файлу")
    doc_type: str | None = Field(None, max_length=50, description="Тип документа")


class DocumentCreate(DocumentBase):
    """Схема для створення нового документа."""

    pass


class DocumentUpdate(BaseModel):
    """Схема для оновлення існуючого документа."""

    title: str | None = Field(None, min_length=1, max_length=255)
    source_url: str | None = Field(None, max_length=512)
    source_file: str | None = Field(None, max_length=255)
    doc_type: str | None = Field(None, max_length=50)


class DocumentResponse(DocumentBase):
    """Схема документа для відповідей API."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
