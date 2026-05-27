from __future__ import annotations

import numpy as np
import ollama

from config.settings import settings


class OllamaEmbedder:
    def __init__(self, model: str = settings.embedding_model, base_url: str = settings.ollama_base_url):
        self.model = model
        self.client = ollama.Client(host=base_url)

    def embed(self, text: str) -> np.ndarray:
        response = self.client.embeddings(model=self.model, prompt=text)
        vector = np.array(response["embedding"], dtype="float32")
        norm = np.linalg.norm(vector)
        if norm:
            vector = vector / norm
        return vector

    def embed_many(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self.embed(text) for text in texts]).astype("float32")
