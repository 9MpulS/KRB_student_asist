# KRB Student Assistant

A RAG-based assistant for Sumy State University students, providing answers to questions about university regulations and normative documents.

## Overview

The system indexes normative documents (PDF, DOCX, etc.) and enables semantic search across their content. Users ask questions in natural language — the assistant retrieves relevant document fragments and generates an answer using an LLM.

**Key features:**

- Upload and index normative documents
- Hybrid search: vector (pgvector) + full-text (Elasticsearch)
- Answer generation via Groq API (LLaMA 3)
- REST API built with FastAPI

## Tech Stack

| Component       | Technology                        |
|-----------------|-----------------------------------|
| Web Framework   | FastAPI                           |
| Database        | PostgreSQL + pgvector             |
| Full-text search| Elasticsearch                     |
| Embeddings      | Ollama (paraphrase-multilingual)  |
| LLM             | Groq API (LLaMA 3)               |
| Package manager | uv                                |

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Docker and Docker Compose
- [Ollama](https://ollama.com/) with the `paraphrase-multilingual` model pulled

### Setup

```bash
git clone <repo-url>
cd KRB_student_asist

# Copy and fill in environment variables
cp .env.example .env
```

### Install dependencies

```bash
uv sync
```

### Start services (PostgreSQL + Elasticsearch)

```bash
docker compose up -d
```

### Initialize the database

```bash
uv run python -c "from src.db.database import init_db; import asyncio; asyncio.run(init_db())"
```

### Run the server

```bash
uv run python main.py
```

API available at: `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`

## Project Structure

```
KRB_student_asist/
├── src/
│   ├── api/          # FastAPI routers and endpoints
│   ├── core/         # Configuration and settings
│   ├── db/           # Database models and repositories
│   ├── schemas/      # Pydantic schemas
│   └── services/     # Business logic: RAG, LLM, indexing
├── main.py           # Application entry point
├── pyproject.toml    # Project dependencies
├── .env.example      # Environment variables template
└── LICENSE
```

## License

MIT — see [LICENSE](LICENSE) for details.
