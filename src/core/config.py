from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Ollama
    OLLAMA_HOST: str = "http://localhost:11434"
    # EMBEDDING_MODEL: str = "nomic-embed-text:latest"
    # EMBEDDING_MODEL: str = "bge-m3:latest"
    EMBEDDING_MODEL: str = "paraphrase-multilingual:latest"
    
    # Groq
    GROQ_API_KEY: str
    LLM_MODEL: str = "openai/gpt-oss-20b"
    
    # App
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    AI_TIMEOUT: int = 60

    CHUNK_SIZE: int = 768
    CHUNK_OVERLAP: int = 150
    
    # Retrieval
    RETRIEVAL_LIMIT_VEC: int = 5
    RETRIEVAL_LIMIT_FTS: int = 5
    RETRIEVAL_LIMIT_ES: int = 5
    
    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ES_INDEX_NAME: str = "krb_chunks"
    
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
