$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/verify_environment.py
Write-Host "Setup complete. Pull models with:"
Write-Host "  ollama pull qwen2.5-coder:3b"
Write-Host "  ollama pull nomic-embed-text"
