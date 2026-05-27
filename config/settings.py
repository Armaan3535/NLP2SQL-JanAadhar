from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    sql_model: str = os.getenv("SQL_MODEL", "qwen2.5-coder:3b")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
    data_dir: Path = PROJECT_ROOT / "data"
    faiss_index_path: Path = PROJECT_ROOT / "data" / "schema.faiss"
    faiss_metadata_path: Path = PROJECT_ROOT / "data" / "schema_metadata.json"
    sqlite_path: Path = PROJECT_ROOT / "data" / "jan_aadhaar_demo.sqlite"
    max_retries: int = int(os.getenv("MAX_SQL_RETRIES", "3"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "16"))

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", f"sqlite:///{self.sqlite_path.as_posix()}")


settings = Settings()
