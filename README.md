# Jan Aadhaar NL2SQL

Local retrieval-augmented Natural Language to SQL for a large Jan Aadhaar-style citizen database.

The system never sends the full schema to the LLM. It embeds table and column metadata with `nomic-embed-text`, retrieves relevant schema fragments from FAISS, builds a reduced prompt, generates SQL with `qwen2.5-coder:3b`, validates the SQL, and returns the query with an optional execution plan.

## Architecture

```text
User question
  -> Ollama embedding
  -> FAISS semantic schema search
  -> relevant tables, columns, relationships
  -> reduced prompt
  -> Ollama Qwen SQL generation
  -> SQL validation and retry
  -> EXPLAIN / index recommendations
```

## Requirements

- Windows laptop with 16 GB RAM
- Python 3.10+
- Ollama installed and running
- No Docker, no cloud API, no external vector database

## Setup

```powershell
python -m pip install -r requirements.txt
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text
python scripts/verify_environment.py
```

Or run:

```powershell
.\scripts\setup.ps1
```

The CLI also checks for missing Ollama models. If a required model is absent it asks permission before running `ollama pull`.

`qwen2.5-coder:3b` is the laptop-friendly default. For more complex queries, switch temporarily with `$env:SQL_MODEL="qwen2.5-coder:7b"`.
The SQL model remains loaded in Ollama for 30 minutes between requests by default to reduce repeated cold-start delay. Override with `$env:OLLAMA_KEEP_ALIVE="10m"` if you prefer lower memory retention.

## Run CLI

```powershell
python app.py --seed-demo-db --build-index "Show all female beneficiaries receiving pension in Jaipur district."
```

Interactive mode:

```powershell
python app.py
```

## Run Streamlit

```powershell
streamlit run app.py
```

In the sidebar, upload an `.xlsx` dummy dataset and select **Load uploaded dataset**. After SQL is generated, the app safely executes the validated `SELECT` query and displays matching entries for verification. Result display is capped by the selected preview limit and can be downloaded as CSV.

Import a workbook from the CLI:

```powershell
python app.py --import-excel "C:\path\to\Dummy_Data_Set.xlsx" --show-results "All boys above 21 in Jaipur"
```

## Project Structure

```text
app.py
config/              settings
database/            SQLAlchemy models, DDL, migrations, demo data
embeddings/          Ollama embeddings and FAISS index
retrieval/           semantic schema retrieval
llm/                 Ollama model management and SQL generation
prompting/           dynamic reduced-context prompt builder
validation/          SQL table, column, join, and safety validation
optimization/        EXPLAIN and index recommendations
evaluation/          benchmark cases and metrics
ui/                  Streamlit UI
tests/               unit tests
docs/                production deployment notes
scripts/             setup and environment verification
```

## Example Questions

- Show all female beneficiaries receiving pension in Jaipur district.
- How many SC category citizens live in Kotputli block?
- List families having NFSA status active and eKYC pending.
- Show top 10 villages with maximum pension beneficiaries.

## Benchmark

```powershell
python -m evaluation.benchmark
```

Metrics include exact match, schema validation, retrieval accuracy, and latency.

## Notes For Real Databases

The bundled SQLite database is for demonstration. For production-scale data, point `DATABASE_URL` at PostgreSQL, Oracle, SQL Server, or another warehouse-backed SQLAlchemy database and preserve the same schema metadata contract.
