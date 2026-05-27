# Production Deployment Guide

## Local Model Runtime

Run Ollama on the same host or a trusted internal machine:

```powershell
ollama serve
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text
```

Set `OLLAMA_BASE_URL` if Ollama is not on `http://localhost:11434`.
Set `OLLAMA_KEEP_ALIVE` to control how long the SQL model remains resident between requests; the laptop-friendly default is `30m`.

## Database Scale

For 8 crore citizens and 2 crore families, do not run analytical workloads on the demo SQLite database. Use a production RDBMS or warehouse with:

- partitioning by district, block, or update date where appropriate
- composite indexes on common filters such as gender, caste, pension status, NFSA status, eKYC status, and geography
- read replicas for NL2SQL workloads
- strict query timeouts and row limits in the execution layer
- audited access controls for citizen data

## Schema Retrieval

The FAISS index contains schema metadata only, not citizen records. Rebuild it whenever tables, columns, synonyms, or descriptions change:

```powershell
python app.py --build-index
```

Add new schema metadata in `database/schema_metadata.py`. Each table and column should include descriptions and aliases because those aliases are what make natural language retrieval work.

## Prompt Safety

The prompt builder sends only:

- retrieved table names
- retrieved column names and descriptions
- relationships needed for joins
- the user question

The full database schema is never sent to the LLM.

## SQL Controls

The validator currently blocks non-SELECT statements and rejects hallucinated tables, hallucinated columns, and undeclared joins. For a production execution service, add:

- mandatory `LIMIT` for list queries
- role-based column masking
- district or department-level authorization predicates
- maximum query timeout
- query allow-list for sensitive tables
- logging of question, retrieved schema, generated SQL, validation result, and execution metadata

## Observability

Track:

- retrieval top-k results and scores
- prompt token size
- generation latency
- validation retry count
- EXPLAIN plan
- query execution time
- rejected SQL reasons
- user feedback on correctness

## Updating Models

The defaults are:

- SQL generation: `qwen2.5-coder:3b` for laptop responsiveness; use `qwen2.5-coder:7b` for more difficult SQL
- embeddings: `nomic-embed-text`

Change them with:

```powershell
$env:SQL_MODEL="qwen2.5-coder:3b"
$env:EMBEDDING_MODEL="nomic-embed-text"
```
