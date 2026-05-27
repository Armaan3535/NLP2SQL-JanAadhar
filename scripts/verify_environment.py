from __future__ import annotations

import importlib
from pathlib import Path
import shutil
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings


PACKAGES = [
    "faiss",
    "ollama",
    "streamlit",
    "sqlalchemy",
    "pandas",
    "numpy",
    "langchain",
    "langchain_community",
    "rapidfuzz",
    "reportlab",
    "openpyxl",
]


def main() -> int:
    ok = True
    print(f"Python: {sys.version.split()[0]}")
    for package in PACKAGES:
        try:
            importlib.import_module(package)
            print(f"[ok] {package}")
        except ImportError:
            ok = False
            print(f"[missing] {package}")
    has_ollama_executable = bool(shutil.which("ollama"))
    if has_ollama_executable:
        print("[ok] ollama executable")
    else:
        print("[warning] ollama executable not on PATH; Python client can still use a reachable Ollama server")
    try:
        response = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        response.raise_for_status()
        models = [model["name"] for model in response.json().get("models", [])]
        print(f"[ok] Ollama server reachable with {len(models)} model(s)")
        for model in [settings.sql_model, settings.embedding_model]:
            available = model in models or model.split(":")[0] in {name.split(":")[0] for name in models}
            ok = ok and available
            print(f"[{'ok' if available else 'missing'}] model {model}")
    except Exception as exc:
        ok = False
        print(f"[warning] Ollama server not reachable: {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
