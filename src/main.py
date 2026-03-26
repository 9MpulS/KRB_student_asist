import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import documents, questions
from src.core.logging import get_logger
from src.db.database import check_db_health, init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Логіка при запуску та зупинці додатка."""
    logger.info("Виконання lifespan startup...")
    await init_db()
    yield
    logger.info("Виконання lifespan shutdown...")


def create_app() -> FastAPI:
    """Ініціалізація та налаштування головного екземпляра FastAPI додатка."""
    tags_metadata = [
        {
            "name": "questions",
            "description": "Операції з питанням-відповіддю RAG асистента. **Головний ендпоінт** системи.",
        },
        {
            "name": "documents",
            "description": "Управління документами: завантаження, індексація, парсинг.",
        },
    ]

    app = FastAPI(
        title="KRB Student Assistant API",
        description="RAG-based API для автоматичних відповідей по нормативних документах СумДУ.",
        version="0.1.0",
        openapi_tags=tags_metadata,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(questions.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")

    # Middleware для логування часу обробки
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        logger.info(f"Запит {request.method} {request.url.path} оброблено за {process_time:.4f} сек")
        response.headers["X-Process-Time"] = str(process_time)
        return response

    @app.get("/health")
    async def health_check():
        """Ендпоінт для моніторингу стану додатку."""
        db_ok = await check_db_health()

        # Перевірка Elasticsearch (опціонально)
        try:
            from src.services.elasticsearch_service import es_service

            _ = await es_service.client.info()
            es_ok = True
        except Exception:
            es_ok = False

        status_code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if db_ok else "degraded",
                "database": "up" if db_ok else "down",
                "elasticsearch": "up" if es_ok else "down",
            },
        )

    # Глобальні обробники помилок
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Необроблена помилка: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error. Please see logs for details."},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Помилка валідації запиту: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors(), "body": exc.body}
        )

    return app


app = create_app()

if __name__ == "__main__":
    logger.info("Starting KRB Student Assistant API...")
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
