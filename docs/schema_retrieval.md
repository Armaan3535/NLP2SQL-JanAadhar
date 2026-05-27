# Schema Retrieval Design

Each table and column becomes a semantic document. A column document includes:

- table name
- column name
- description
- data type
- aliases and synonyms
- sample values where useful
- indexed status

Example:

```json
{
  "table": "member",
  "column": "gender",
  "description": "Citizen gender male female other",
  "aliases": ["gender", "sex", "male", "female", "woman", "man"]
}
```

At runtime the user question is embedded with Ollama, searched against the FAISS index, and converted into a compact schema context. Join keys are added only when both sides of a relationship are already relevant.

This keeps prompts small even when the real schema grows to hundreds or thousands of columns.
