from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from config.settings import settings
from database.schema_metadata import COLUMNS, TABLES
from embeddings.ollama_embeddings import OllamaEmbedder


def schema_documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for table in TABLES:
        docs.append(
            {
                "kind": "table",
                "table": table.table,
                "column": None,
                "text": f"table {table.table}. {table.description}. aliases: {', '.join(table.aliases)}",
                "metadata": asdict(table),
            }
        )
    for column in COLUMNS:
        docs.append(
            {
                "kind": "column",
                "table": column.table,
                "column": column.column,
                "qualified_name": column.qualified_name,
                "text": (
                    f"column {column.qualified_name}. semantic name: {column.business_name}. {column.description}. "
                    f"type: {column.data_type}. aliases: {', '.join(column.aliases)}. "
                    f"sample values: {', '.join(column.sample_values)}"
                ),
                "metadata": asdict(column),
            }
        )
    return docs


class FaissSchemaStore:
    def __init__(
        self,
        index_path: Path = settings.faiss_index_path,
        metadata_path: Path = settings.faiss_metadata_path,
        embedder: OllamaEmbedder | None = None,
    ):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedder = embedder or OllamaEmbedder()
        self.index: faiss.Index | None = None
        self.documents: list[dict[str, Any]] = []

    def build(self, force: bool = False) -> None:
        if self.index_path.exists() and self.metadata_path.exists() and not force:
            self.load()
            return
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.documents = schema_documents()
        vectors = self.embedder.embed_many([doc["text"] for doc in self.documents])
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)
        faiss.write_index(self.index, str(self.index_path))
        self.metadata_path.write_text(json.dumps(self.documents, indent=2), encoding="utf-8")

    def load(self) -> None:
        self.index = faiss.read_index(str(self.index_path))
        self.documents = json.loads(self.metadata_path.read_text(encoding="utf-8"))

    def search(self, query: str, top_k: int = settings.retrieval_top_k) -> list[dict[str, Any]]:
        if self.index is None:
            self.build()
        assert self.index is not None
        query_vector = self.embedder.embed(query).reshape(1, -1)
        scores, indexes = self.index.search(query_vector, top_k)
        results: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], indexes[0]):
            if idx < 0:
                continue
            doc = dict(self.documents[idx])
            doc["score"] = float(score)
            results.append(doc)
        return results
