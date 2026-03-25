import time
from datetime import datetime

from groq import AsyncGroq

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Сервіс для генерації відповідей на основі RAG через Groq API."""

    def __init__(self):
        """Ініціалізація асинхронного клієнта Groq."""
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=settings.AI_TIMEOUT)
        self.model = settings.LLM_MODEL
        self.system_prompt = (
            "Ти асистент для студентів СумДУ. "
            "Відповідай коротко та ввічливо українською мовою на основі наданого контексту. "
            "Якщо відповіді немає в контексті — чесно скажи про це."
        )
        logger.info(f"LLMService ініціалізовано з моделлю: {self.model} (timeout: {settings.AI_TIMEOUT}s)")

    async def generate_answer(self, query: str, context: str) -> str:
        """
        Формує запит та отримує відповідь від Groq.

        Args:
            query: Запит користувача.
            context: Контекст з бази знань.

        Returns:
            str: Текст відповіді.
        """
        try:
            logger.info("Надсилання запиту до Groq")
            # Просте обмеження контексту (наприклад, 40к символів ~ 10-12к токенів)
            safe_context = context[:40000]
            if len(context) > 40000:
                logger.warning(f"Контекст занадто великий ({len(context)}), обрізано до 40000")

            start_time = time.perf_counter()
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Контекст: {safe_context}\n\nПитання: {query}"},
                ],
                model=self.model,
                temperature=0.1,  # Низька температура для більш точних відповідей
            )
            duration = time.perf_counter() - start_time
            logger.debug(f"Groq request took {duration:.2f}s")

            answer = chat_completion.choices[0].message.content
            logger.info("Відповідь успішно отримана від Groq")
            return answer
        except Exception as e:
            logger.error(f"Помилка при запиті до Groq (generate_answer): {e}")
            raise

    async def generate_fts_query(self, query: str) -> str:
        """
        Перетворює запит користувача на набір ключових слів для повнотекстового пошуку (FTS).

        Args:
            query: Текст запиту користувача.

        Returns:
            str: Рядок із ключовими словами, поєднаними OR/AND.
        """
        system_prompt = (
            "Твоє завдання — перетворити природний запит користувача на рядок ключових слів для повнотекстового пошуку. "
            "Використовуй оператори OR (для синонімів) та AND (для поєднання обов'язкових термінів). "
            "Повертай ТІЛЬКИ готовий рядок запиту. Жодних вступів, лапок чи пояснень. "
            "Приклад: 'За що мене можуть відрахувати?' -> 'відрахування OR відрахувати OR виключення OR припинення навчання'"
        )

        try:
            logger.info(f"Генерація FTS запиту для: {query}")
            chat_completion = await self.client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                model=self.model,
                temperature=0.0,  # Максимальна детермінованість
            )

            fts_query = chat_completion.choices[0].message.content.strip()
            # Видаляємо можливі лапки, якщо модель їх додала
            fts_query = fts_query.replace('"', "").replace("'", "")

            logger.info(f"Сгенеровано FTS запит: {fts_query}")
            return fts_query
        except Exception as e:
            logger.error(f"Помилка при генерації FTS запиту: {e}")
            raise

    async def rerank_chunks(self, query: str, chunks: list) -> list:
        """
        Оцінює релевантність чанків запиту за допомогою LLM та сортує їх.
        Батчить чанки по 2 для економії запитів.
        """
        if not chunks:
            return []

        logger.info(f"Ранжування {len(chunks)} чанків за допомогою LLM")
        scored_chunks = []

        # Промпт для ранкера
        ranker_system_prompt = (
            "Ти є ранкером (оцінювачем) релевантності у системі RAG (Retrieval-Augmented Generation).\n\n"
            "Тобі буде надано запит та фрагменти тексту, отримані у результаті пошуку, пов'язані із цим запитом. "
            "Твоє завдання — оцінити та виставити бал кожному фрагменту відповідно до його релевантності щодо заданого запиту.\n\n"
            "Інструкція:\n\n"
            "1. Оцінка релевантності (від 0 до 1 з кроком 0.1):\n"
            "   0 = Повністю не релевантний: фрагмент не має жодного зв’язку із запитом.\n"
            "   0.1 = Майже не релевантний: дуже слабкий або туманний зв’язок.\n"
            "   0.2 = Дуже слабко релевантний: мінімальний або дотичний зв’язок.\n"
            "   0.3 = Слабко релевантний: стосується лише невеликого аспекту запиту, без суттєвих деталей.\n"
            "   0.4 = Частково релевантний: містить деяку пов’язану інформацію, але не повністю.\n"
            "   0.5 = Помірно релевантний: стосується запиту, але поверхнево або частково.\n"
            "   0.6 = Досить релевантний: надає релевантну інформацію, але без глибини або конкретики.\n"
            "   0.7 = Релевантний: чітко пов’язаний із запитом, має суттєвий зміст, але не повністю вичерпний.\n"
            "   0.8 = Дуже релевантний: тісно пов’язаний із запитом і надає важливу інформацію.\n"
            "   0.9 = Високо релевантний: майже повністю відповідає на запит, має детальну та конкретну інформацію.\n"
            "   1 = Повністю релевантний: прямо і вичерпно відповідає на запит, з усією необхідною конкретикою.\n\n"
            "2. Поверни ТІЛЬКИ бали через кому або з нового рядка. Жодного іншого тексту."
        )

        # Розбиваємо на батчі по 2
        for i in range(0, len(chunks), 2):
            batch = chunks[i : i + 2]

            user_content = f"Запит: {query}\n\n"
            for idx, chunk in enumerate(batch):
                user_content += f"Фрагмент {idx + 1}: {chunk.content[:1000]}\n\n"

            user_content += "Поверни бали для кожного фрагмента:"

            try:
                chat_completion = await self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": ranker_system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    model=self.model,
                    temperature=0.0,
                )

                response_text = chat_completion.choices[0].message.content.strip()
                logger.debug(f"Ранкер батч {i // 2 + 1} відповідь: {response_text}")

                # Знаходимо всі числа в тексті
                import re

                scores = []
                for val in re.findall(r"0\.\d|1\.0|1|0", response_text):
                    try:
                        scores.append(float(val))
                    except ValueError:
                        continue

                # Призначаємо бали чанкам (якщо модель повернула менше балів, решта отримує 0)
                for j, chunk in enumerate(batch):
                    score = scores[j] if j < len(scores) else 0.0
                    scored_chunks.append((chunk, score))

            except Exception as e:
                logger.error(f"Помилка при ранжуванні батчу {i // 2 + 1}: {e}")
                for chunk in batch:
                    scored_chunks.append((chunk, 0.0))

        # Сортуємо за балом спаданням
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Фільтруємо за порогом релевантності (>= 0.8 як просив користувач)
        filtered_chunks = [item for item in scored_chunks if item[1] >= 0.8]

        # Обмежуємо кількість до 3 найкращих
        final_selection = filtered_chunks[:3]

        # Записуємо результати у файл (всі результати для аналізу, але з поміткою про фільтр та вибір)
        try:
            with open("reranking_log.txt", "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(f"Запит: {query}\n")
                f.write(
                    f"Знайдено: {len(scored_chunks)}, Відібрано (>=0.8): {len(filtered_chunks)}, Обрано для RAG: {len(final_selection)}\n"
                )
                for chunk, score in scored_chunks:
                    source = chunk.page.document.title if chunk.page and chunk.page.document else "Невідоме джерело"
                    page = f"(стор. {chunk.page.page_number})" if chunk.page else ""
                    is_selected = any(chunk.id == sel[0].id for sel in final_selection)
                    status = "[V]" if is_selected else ("[?]" if score >= 0.8 else "[X]")
                    f.write(f"{status} {source} {page} - {score}\n")
                f.write("-" * 30 + "\n")
        except Exception as e:
            logger.error(f"Помилка при записі логу ранжування: {e}")

        # Логуємо результати для відладки
        for chunk, score in final_selection:
            logger.info(
                f"Rerank top result (selected): {score} - {chunk.page.document.title if chunk.page else 'Unknown'}"
            )

        return [item[0] for item in final_selection]
