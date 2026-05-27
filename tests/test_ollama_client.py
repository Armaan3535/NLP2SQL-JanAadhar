from llm.ollama_client import OllamaModelManager


class StubModelManager(OllamaModelManager):
    def list_models(self) -> set[str]:
        return {"qwen2.5-coder:7b", "nomic-embed-text:latest"}


def test_tagged_model_requires_exact_tag():
    manager = StubModelManager()
    assert manager.has_model("qwen2.5-coder:7b")
    assert not manager.has_model("qwen2.5-coder:3b")


def test_untagged_model_accepts_latest_tag():
    manager = StubModelManager()
    assert manager.has_model("nomic-embed-text")
