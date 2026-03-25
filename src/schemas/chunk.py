from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChunkResponse(BaseModel):
    """Схема для представлення шматка тексту у відповідях API."""

    id: UUID
    page_id: UUID
    content: str = Field(..., description="Текст шматка")
    chunk_index: int = Field(..., description="Порядковий номер шматка в документі")
    meta_data: dict | None = Field(default=None, description="Додаткові метадані чанка")

    model_config = ConfigDict(from_attributes=True)


class ChunkSearchResult(ChunkResponse):
    """Схема для результату векторного пошуку."""

    score: float = Field(..., description="Оцінка схожості або відстань")
