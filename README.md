# 🎓 KRB Student Assistant

RAG-асистент для студентів СумДУ, що дозволяє отримувати відповіді на запитання щодо нормативних документів університету на основі технології Retrieval-Augmented Generation (RAG).

## 📌 Опис проєкту

Система індексує нормативні документи (PDF, DOCX тощо) та забезпечує семантичний пошук по їх змісту. Користувач ставить запитання природною мовою — асистент знаходить релевантні фрагменти документів і генерує відповідь за допомогою LLM.

### Основні можливості

- 📄 Завантаження та індексація нормативних документів
- 🔍 Гібридний пошук: векторний (pgvector) + повнотекстовий (Elasticsearch)
- 🤖 Генерація відповідей через Groq API (LLaMA)
- 🌐 REST API на базі FastAPI
- 🐳 Повна підтримка Docker

## 🛠️ Технологічний стек

| Компонент | Технологія |
|-----------|------------|
| Web Framework | FastAPI |
| Database | PostgreSQL + pgvector |
| Full-text search | Elasticsearch |
| Embeddings | Ollama (paraphrase-multilingual) |
| LLM | Groq API (LLaMA 3) |
| Package manager | uv |

## 🚀 Запуск проєкту

### Передумови

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Docker & Docker Compose
- [Ollama](https://ollama.com/) із завантаженою моделлю `paraphrase-multilingual`

### 1. Клонування та налаштування

```bash
git clone <repo-url>
cd KRB_student_asist

# Скопіюйте та заповніть .env
cp .env.example .env
```

### 2. Встановлення залежностей

```bash
uv sync
```

### 3. Запуск сервісів (PostgreSQL + Elasticsearch)

```bash
docker compose up -d
```

### 4. Ініціалізація БД

```bash
uv run python scripts/init_db.py
```

### 5. Запуск сервера

```bash
uv run python main.py
```

API буде доступне за адресою: `http://localhost:8000`  
Документація: `http://localhost:8000/docs`

## 🧪 Тестування

```bash
uv run pytest
```

## 📁 Структура проєкту

```
KRB_student_asist/
├── src/
│   ├── api/          # FastAPI роутери
│   ├── core/         # Налаштування, конфіг
│   ├── db/           # Моделі БД, репозиторії
│   ├── schemas/      # Pydantic схеми
│   └── services/     # Бізнес-логіка (RAG, LLM, індексація)
├── scripts/          # Утилітарні скрипти
├── tests/            # Тести
├── retrieval_benchmark/ # Бенчмарки пошуку
├── main.py           # Точка входу
├── pyproject.toml    # Залежності проєкту
├── init_db.sql       # SQL-схема бази даних
├── .env.example      # Приклад змінних середовища
└── LICENSE
```

## 📝 Ліцензія

MIT — деталі у файлі [LICENSE](LICENSE).
