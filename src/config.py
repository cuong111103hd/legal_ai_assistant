"""
Centralized configuration using Pydantic BaseSettings.
All settings are loaded from environment variables / .env file.
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Load environment variables from .env into os.environ for LangChain tracing
load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation."""

    # --- LLM ---
    LLM_PROVIDER: str = Field(default="groq", description="LLM provider: 'groq' or 'openai'")
    GROQ_API_KEY: str = Field(default="", description="Groq API key")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    LLM_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="LLM model name (e.g., 'gpt-4o' for OpenAI or 'llama-3.3-70b-versatile' for Groq)",
    )
    LLM_TEMPERATURE: float = Field(default=0.1, description="LLM temperature")
    LLM_MAX_TOKENS: int = Field(default=4096, description="Max tokens for LLM response")

    # --- Qdrant ---
    QDRANT_HOST: str = Field(default="localhost", description="Qdrant server host")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant server port")
    QDRANT_COLLECTION: str = Field(
        default="vietnamese_legal",
        description="Qdrant collection name",
    )
    QDRANT_IN_MEMORY: bool = Field(
        default=False,
        description="Use in-memory Qdrant (no Docker needed, for dev only)",
    )

    # --- PostgreSQL ---
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    POSTGRES_DB: str = Field(default="legal_assistant", description="PostgreSQL database name")
    POSTGRES_USER: str = Field(default="legal_user", description="PostgreSQL user")
    POSTGRES_PASSWORD: str = Field(default="legal_pass", description="PostgreSQL password")

    @property
    def POSTGRES_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def POSTGRES_URL_SYNC(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # --- Embedding ---
    EMBEDDING_MODEL: str = Field(
        default="Quockhanh05/Vietnam_legal_embeddings",
        description="HuggingFace embedding model ID",
    )
    EMBEDDING_DIM: int = Field(default=768, description="Embedding vector dimension")
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        description="Batch size for embedding generation (tune for RAM)",
    )

    # --- Dataset ---
    DATASET_NAME: str = Field(
        default="th1nhng0/vietnamese-legal-documents",
        description="HuggingFace dataset ID",
    )

    # --- Chunking ---
    CHUNK_SIZE: int = Field(default=1000, description="Max characters per chunk")
    CHUNK_OVERLAP: int = Field(default=200, description="Overlap between chunks")

    # --- Retrieval ---
    TOP_K: int = Field(default=10, description="Number of results to retrieve")
    RRF_K: int = Field(default=60, description="RRF constant k")
    CONTEXT_WINDOW: int = Field(
        default=1,
        description="Number of adjacent articles to fetch for context injection",
    )

    # --- Paths ---
    BM25_INDEX_PATH: str = Field(
        default="data/bm25_index.pkl",
        description="Path to persist BM25 index",
    )
    CHUNKS_METADATA_PATH: str = Field(
        default="data/chunks_metadata.pkl",
        description="Path to persist chunk metadata for BM25",
    )

    # --- API ---
    API_HOST: str = Field(default="0.0.0.0", description="API server host")
    API_PORT: int = Field(default=8000, description="API server port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_HTTPX: bool = Field(
        default=False,
        description="Whether to show verbose HTTP logs from httpx/huggingface_hub",
    )

    # --- Legacy (kept for compatibility) ---
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")

    # --- LangChain / LangSmith ---
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_API_KEY: str = Field(default="")
    LANGCHAIN_PROJECT: str = Field(default="legal-ai-assistant")
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
