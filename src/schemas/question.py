from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Схема для запиту з питанням користувача."""
    question: str = Field(
        ..., 
        min_length=3, 
        max_length=1000, 
        description="Питання користувача до асистента"
    )


class QuestionResponse(BaseModel):
    """Схема для відповіді на питання."""
    answer: str = Field(..., description="Згенерована відповідь асистента")
    sources: List[str] = Field(default_factory=list, description="Список джерел інформації")
    context: Optional[str] = Field(None, description="Контекст, що був використаний для генерації (для відладки)")
