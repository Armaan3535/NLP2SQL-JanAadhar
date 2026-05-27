from __future__ import annotations

import argparse
from dataclasses import dataclass

from config.settings import settings
from database.excel_importer import import_excel_dataset
from database.query_results import execute_select_preview
from database.sample_data import seed_demo_data
from embeddings.faiss_store import FaissSchemaStore
from llm.ollama_client import OllamaModelManager, OllamaSqlGenerator
from normalization.query_normalizer import normalize_query
from optimization.query_optimizer import OptimizationReport, QueryOptimizer
from prompting.prompt_builder import PromptBuilder
from retrieval.schema_retriever import SchemaRetriever
from validation.sql_validator import SQLValidator

from database.schema_metadata import RAJASTHAN_DISTRICTS_41


@dataclass
class PipelineOutput:
    question: str
    normalized_question: str
    query_corrections: dict[str, str]
    sql: str
    retrieved_tables: list[str]
    retrieved_columns: list[str]
    confidence: float
    validation_errors: list[str]
    optimization: OptimizationReport | None


def _post_process_sql(sql: str) -> str:
    """
    Post-process LLM-generated SQL to fix predictable systematic errors:
    1. Free-text columns: always use LIKE for partial matching
    2. bank_name: always case-insensitive via UPPER()
    3. Categorical casing: normalize all variants of gender, caste_category, marital_status
    4. education: fix the 'illiterate' lowercase anomaly; LIKE for all others
    5. is_rural: map text/boolean to integer 0 or 1
    6. District casing: fix case of known Rajasthan district names
    7. District redirect: non-district locations → block OR village search
    """
    import re

    # ── Step 1: Free-text columns → LIKE '%val%' ─────────────────────────────
    # Exact '=' will fail for names, castes, villages, occupations etc. because
    # the DB has mixed casing, full names with suffixes, and spelling variants.
    def text_replacer(match):
        col = match.group(1)
        val = match.group(2)
        return f"{col} LIKE '%{val}%'"

    _FREE_TEXT_COLS = (
        "member_name|father_name|mother_name|spouse_name|family_head_name"
        "|caste|city|block|gram_panchayat|village|occupation"
    )
    sql = re.sub(
        rf"\b((?:\w+\.)?(?:{_FREE_TEXT_COLS}))\s*=\s*'([^']+)'",
        text_replacer, sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        rf'\b((?:\w+\.)?(?:{_FREE_TEXT_COLS}))\s*=\s*"([^"]+)"',
        text_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 2: bank_name → UPPER(col) LIKE '%UPPER_VAL%' ───────────────────
    # Bank names are stored inconsistently (UPPER, Title, mixed) in real data.
    # Wrapping both sides in UPPER() guarantees a case-insensitive match.
    def bank_replace_safe(match):
        col = match.group(1)
        val = match.group(2).strip()
        return f"UPPER({col}) LIKE '%{val.upper()}%'"

    sql = re.sub(
        r"\b((?:\w+\.)?bank_name)\s*=\s*'([^']+)'",
        bank_replace_safe, sql, flags=re.IGNORECASE,
    )
    # Also normalize existing LIKE patterns that aren't already UPPER-wrapped
    sql = re.sub(
        r"\b((?:\w+\.)?bank_name)\s*LIKE\s*'%([^'%]+)%'",
        lambda m: (
            m.group(0) if m.group(0).upper().startswith("UPPER(")
            else f"UPPER({m.group(1)}) LIKE '%{m.group(2).strip().upper()}%'"
        ),
        sql, flags=re.IGNORECASE,
    )

    # ── Step 3: Categorical value normalization ───────────────────────────────
    # The real dataset will have GEN/General/GENERAL/general, Widow/widow/WIDOW,
    # Male/male/MALE, etc. Normalize everything to the canonical stored value.
    def cat_replacer(match):
        col_raw = match.group(1)
        col = col_raw.lower()
        val = match.group(2).strip()
        val_l = val.lower()

        if "gender" in col:
            if val_l in ("male", "m"):
                return f"{col_raw} = 'Male'"
            if val_l in ("female", "f"):
                return f"{col_raw} = 'Female'"

        elif "caste_category" in col:
            # All SC variants
            if val_l in ("sc", "scheduled caste", "dalit"):
                return f"{col_raw} = 'SC'"
            # All ST variants
            if val_l in ("st", "scheduled tribe", "tribal", "adivasi"):
                return f"{col_raw} = 'ST'"
            # All OBC variants
            if val_l in ("obc", "other backward class", "other backward caste",
                         "other backward", "backward class"):
                return f"{col_raw} = 'OBC'"
            # All GEN variants — this is the most common mismatch
            if val_l in ("gen", "general", "general category", "open",
                         "unreserved", "ur", "forward", "forward caste"):
                return f"{col_raw} = 'GEN'"
            # Handle UPPER() already applied: SC/ST/OBC/GEN exact
            return f"{col_raw} = '{val.upper()}'"

        elif "marital_status" in col:
            if val_l in ("married",):
                return f"{col_raw} = 'Married'"
            if val_l in ("unmarried", "single", "never married", "bachelor",
                         "spinster"):
                return f"{col_raw} = 'Unmarried'"
            if val_l in ("widow", "widowed", "widower"):
                return f"{col_raw} = 'Widow'"

        return match.group(0)

    _CAT_COLS = r"gender|caste_category|marital_status"
    sql = re.sub(
        rf"\b((?:\w+\.)?(?:{_CAT_COLS}))\s*=\s*'([^']+)'",
        cat_replacer, sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        rf'\b((?:\w+\.)?(?:{_CAT_COLS}))\s*=\s*"([^"]+)"',
        cat_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 4: education — 'illiterate' is stored lowercase; others Title Case ─
    # Use LOWER() for illiterate to match regardless of DB casing.
    # For all other education values use LIKE for partial/case-insensitive match.
    def edu_replacer(match):
        col = match.group(1)
        val = match.group(2).strip()
        if val.lower() == "illiterate":
            return f"LOWER({col}) = 'illiterate'"
        # For education already handled by Step 1 LIKE rewrite, this won't fire.
        # This handles any remaining exact = 'Graduate' etc.
        return f"{col} LIKE '%{val}%'"

    sql = re.sub(
        r"\b((?:\w+\.)?education)\s*=\s*'([^']+)'",
        edu_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 5: is_rural — DB stores INTEGER 0 (urban) or 1 (rural) ──────────
    def rural_replacer(match):
        col = match.group(1)
        val = match.group(2).strip().lower().strip("'\"")
        if val in ("true", "1", "rural", "yes"):
            return f"{col} = 1"
        if val in ("false", "0", "urban", "no"):
            return f"{col} = 0"
        return match.group(0)

    sql = re.sub(
        r"\b((?:\w+\.)?is_rural)\s*=\s*['\"]?(\w+)['\"]?",
        rural_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 6: District casing normalization (known districts only) ──────────
    def district_exact_replacer(match):
        col = match.group(1)
        val = match.group(2).strip().lower()
        for canonical_district in RAJASTHAN_DISTRICTS_41:
            if val == canonical_district.lower():
                return f"{col} = '{canonical_district}'"
        # Not a known district — Step 7 will redirect it
        return match.group(0)

    sql = re.sub(
        r"\b((?:\w+\.)?district)\s*=\s*'([^']+)'",
        district_exact_replacer, sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r'\b((?:\w+\.)?district)\s*=\s*"([^"]+)"',
        district_exact_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 7: Redirect district → block/village for non-district locations ──
    known_districts_lower = {d.lower() for d in RAJASTHAN_DISTRICTS_41}

    redirect_pattern = (
        r"\b((?:[A-Za-z_]\w*\.)?)district"
        r"\s*(?:=\s*'([^']+)'|LIKE\s*'%([^'%]+)%')"
    )

    def district_redirect_full(match):
        prefix = match.group(1) or ""
        val = (match.group(2) or match.group(3) or "").strip()
        if not val or val.lower() in known_districts_lower:
            return match.group(0)
        return f"({prefix}block LIKE '%{val}%' OR {prefix}village LIKE '%{val}%')"

    sql = re.sub(redirect_pattern, district_redirect_full, sql, flags=re.IGNORECASE)

    return sql


def generate_sql_pipeline(
    question: str,
    ask_model_pull: bool = True,
    include_optimization: bool = True,
    run_query_for_profile: bool = False,
) -> PipelineOutput:
    manager = OllamaModelManager()
    manager.ensure_model(settings.sql_model, ask_permission=ask_model_pull)
    manager.ensure_model(settings.embedding_model, ask_permission=ask_model_pull)

    store = FaissSchemaStore()
    store.build()
    normalized = normalize_query(question)
    retrieval = SchemaRetriever(store).retrieve(normalized.normalized)
    prompt_builder = PromptBuilder()
    generator = OllamaSqlGenerator()
    validator = SQLValidator()

    previous_error: str | None = None
    sql = ""
    validation_errors: list[str] = []
    final_sql_is_valid = False
    for _ in range(settings.max_retries):
        prompt = prompt_builder.build(retrieval, previous_error=previous_error)
        sql = generator.generate(prompt)
        sql = _post_process_sql(sql)
        validation = validator.validate(
            sql,
            allowed_tables=retrieval.tables,
            allowed_columns=retrieval.columns,
        )
        validation_errors = validation.errors
        if validation.valid:
            final_sql_is_valid = True
            break
        previous_error = "; ".join(validation.errors)

    optimization = None
    if include_optimization and sql and final_sql_is_valid:
        validation = validator.validate(sql, allowed_tables=retrieval.tables, allowed_columns=retrieval.columns)
        if validation.valid:
            optimization = QueryOptimizer().profile(sql, run_query=run_query_for_profile)

    return PipelineOutput(
        question=question,
        normalized_question=normalized.normalized,
        query_corrections=normalized.corrections,
        sql=sql if final_sql_is_valid else "",
        retrieved_tables=retrieval.tables,
        retrieved_columns=retrieval.columns,
        confidence=retrieval.confidence,
        validation_errors=validation_errors,
        optimization=optimization,
    )


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Local Jan Aadhaar-style Natural Language to SQL generator.")
    parser.add_argument("question", nargs="*", help="Natural language question to convert into SQL.")
    parser.add_argument("--build-index", action="store_true", help="Force rebuild the FAISS schema index.")
    parser.add_argument("--seed-demo-db", action="store_true", help="Create and seed the SQLite demo database.")
    parser.add_argument("--import-excel", help="Replace the local demo data with an Excel dummy dataset.")
    parser.add_argument("--show-results", action="store_true", help="Display up to 20 matching database rows after generating SQL.")
    parser.add_argument("--no-explain", action="store_true", help="Skip EXPLAIN query plan generation.")
    parser.add_argument("--run-profile-query", action="store_true", help="Execute the generated SQL while profiling.")
    args = parser.parse_args()

    if args.seed_demo_db:
        seed_demo_data()
        print(f"Demo database ready at {settings.sqlite_path}")
    if args.import_excel:
        report = import_excel_dataset(args.import_excel)
        print(
            f"Imported {report.members_loaded} members, {report.families_loaded} family records, "
            f"and {report.bank_records_loaded} bank records from {report.source_name}."
        )
        print("This workbook has no scheme benefit or verification fields; those local tables are empty.")

    manager = OllamaModelManager()
    manager.ensure_model(settings.sql_model)
    manager.ensure_model(settings.embedding_model)

    if args.build_index:
        FaissSchemaStore().build(force=True)
        print(f"FAISS schema index rebuilt at {settings.faiss_index_path}")

    question = " ".join(args.question).strip()
    if not question:
        question = input("Ask a Jan Aadhaar database question: ").strip()
    output = generate_sql_pipeline(
        question,
        ask_model_pull=False,
        include_optimization=not args.no_explain,
        run_query_for_profile=args.run_profile_query,
    )
    print("\nGenerated SQL")
    print(output.sql)
    print("\nRetrieved tables")
    print(", ".join(output.retrieved_tables))
    print("\nRetrieved columns")
    print(", ".join(output.retrieved_columns))
    print(f"\nConfidence: {output.confidence}")
    if output.query_corrections:
        print("\nQuery spelling corrections")
        print(", ".join(f"{source} -> {target}" for source, target in output.query_corrections.items()))
        print(f"Normalized question: {output.normalized_question}")
    if output.validation_errors:
        print("\nValidation errors")
        print("; ".join(output.validation_errors))
    if args.show_results and output.sql:
        preview = execute_select_preview(output.sql, max_rows=20)
        print("\nMatching entries")
        print(preview.rows.to_string(index=False) if not preview.rows.empty else "No matching entries.")
        if preview.truncated:
            print("Showing the first 20 rows only.")
    if output.optimization:
        print("\nExecution plan")
        print("\n".join(output.optimization.execution_plan))
        print(f"\nPlanning/explain time: {output.optimization.execution_time_ms} ms")
        if output.optimization.index_recommendations:
            print("\nIndex recommendations")
            print("\n".join(output.optimization.index_recommendations))


def _is_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__":
    if _is_streamlit():
        from ui.streamlit_app import render

        render()
    else:
        run_cli()
