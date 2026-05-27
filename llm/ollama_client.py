from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass

import ollama
import requests

from config.settings import settings


class OllamaUnavailableError(RuntimeError):
    pass


def _is_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


@dataclass
class OllamaModelManager:
    base_url: str = settings.ollama_base_url

    def list_models(self) -> set[str]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaUnavailableError(
                "Ollama is not reachable. Start Ollama, then retry."
            ) from exc
        return {model["name"] for model in response.json().get("models", [])}

    def has_model(self, model_name: str) -> bool:
        available = self.list_models()
        if ":" in model_name:
            return model_name in available
        return model_name in available or f"{model_name}:latest" in available

    def ensure_model(self, model_name: str, ask_permission: bool = True) -> None:
        if self.has_model(model_name):
            return
            
        if _is_streamlit():
            # If running in Streamlit, interactive stdin 'input()' is not supported
            if not ask_permission:
                # If checkbox is unchecked, raise a descriptive exception
                raise RuntimeError(
                    f"Required Ollama model '{model_name}' is not installed locally. "
                    f"Please check 'Pull missing Ollama models' in the sidebar or run "
                    f"'ollama pull {model_name}' in your terminal."
                )
            # If checkbox is checked, we proceed directly with pulling without input() prompt
        else:
            # Running in CLI, standard input is available
            if ask_permission:
                answer = input(f"Ollama model '{model_name}' is missing. Pull it now? [y/N]: ").strip().lower()
                if answer not in {"y", "yes"}:
                    raise RuntimeError(f"Required model '{model_name}' is not installed.")
                    
        if shutil.which("ollama"):
            subprocess.run(["ollama", "pull", model_name], check=True)
        else:
            ollama.Client(host=self.base_url).pull(model_name)


class OllamaSqlGenerator:
    def __init__(self, model: str = settings.sql_model, base_url: str = settings.ollama_base_url):
        self.model = model
        self.client = ollama.Client(host=base_url)

    def generate(self, prompt: str) -> str:
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            keep_alive=settings.ollama_keep_alive,
            options={
                "temperature": 0,
                "top_p": 0.1,
                "num_ctx": 2048,
                "num_predict": 256,
            },
        )
        return _clean_sql(response["response"])


def _clean_sql(text: str) -> str:
    sql = text.strip()
    if sql.startswith("```"):
        sql = sql.strip("`")
        sql = sql.replace("sql\n", "", 1).replace("SQL\n", "", 1)
    return sql.strip().rstrip(";") + ";"
