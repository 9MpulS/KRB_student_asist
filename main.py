import asyncio

from src.db.database import AsyncSessionLocal
from src.services.rag_service import RAGService


async def main():
    async with AsyncSessionLocal() as session:
        rag_service = RAGService(session)
        result = await rag_service.ask_question("Як застосовується замісник?")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
