from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Схема для запиту з питанням користувача."""

    question: str = Field(..., min_length=3, max_length=1000, description="Питання користувача до асистента")

    model_config = {
        "json_schema_extra": {"example": {"question": "Який порядок відрахування студентів за неуспішність?"}}
    }


class QuestionResponse(BaseModel):
    """Схема для відповіді на питання."""

    answer: str = Field(..., description="Згенерована відповідь асистента")
    sources: list[str] = Field(default_factory=list, description="Список джерел інформації")
    context: str | None = Field(None, description="Контекст, що був використаний для генерації (для відладки)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "Студент може бути відрахований у разі отримання 3 і більше незадовільних оцінок під час сесії...",
                "sources": ["Положення про організацію освітнього процесу (стор. 15)"],
                "context": None,
            }
        }
    }
