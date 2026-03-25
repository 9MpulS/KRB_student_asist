from fastapi import APIRouter, Depends, HTTPException, status
import groq
import httpx
from src.schemas.question import QuestionRequest, QuestionResponse
from src.services.rag_service import RAGService
from src.api.dependencies import get_rag_service
from src.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/questions", tags=["questions"])

@router.post("", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest, 
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Обробити питання користувача через RAG пайплайн.
    """
    logger.info(f"API запит: питання '{request.question}'")
    try:
        response = await rag_service.ask_question(request.question)
        return response
    except (groq.APITimeoutError, httpx.TimeoutException) as e:
        logger.error(f"Timeout при зверненні до AI сервісів: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, 
            detail="AI service timeout. Please try again later."
        )
    except (groq.APIConnectionError, httpx.ConnectError) as e:
        logger.error(f"Помилка з'єднання з AI сервісами: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="AI service unavailable. Please check backend connection."
        )
    except Exception as e:
        logger.error(f"Помилка при обробці питання в API: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal server error during RAG processing"
        )
