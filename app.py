from __future__ import annotations

import argparse
from dataclasses import dataclass

from config.settings import settings
from database.excel_importer import import_excel_dataset
from database.query_results import execute_select_preview
from embeddings.faiss_store import FaissSchemaStore
from llm.ollama_client import OllamaModelManager, OllamaSqlGenerator
from normalization.query_normalizer import normalize_query
from optimization.query_optimizer import OptimizationReport, QueryOptimizer
from prompting.prompt_builder import PromptBuilder
from retrieval.schema_retriever import SchemaRetriever
from validation.sql_validator import SQLValidator

from database.schema_metadata import RAJASTHAN_DISTRICTS_41

# ── Module-level lookups ─────────────────────────────────────────────────────
# Pre-built for O(1) access inside _post_process_sql on every call.
_DISTRICTS_LOWER    = {d.lower() for d in RAJASTHAN_DISTRICTS_41}
_DISTRICT_CANONICAL = {d.lower(): d for d in RAJASTHAN_DISTRICTS_41}

# Phrases that signal an "unbanked / no bank account" query
_NO_BANK_WORDS = [
    "no bank", "without bank", "don't have", "do not have",
    "no account", "unbanked", "without account",
]

# Phrases that signal the user explicitly asked about member_type
_MEMBER_TYPE_WORDS = [
    "regular member", "mem type", "member type", "hof", "head of family",
]

_CASTE_GROUPS = [
    {"rajput", "rajpoot", "राजपूत"},
    {"jat", "जाट"},
    {"mina", "meena", "मीना"},
    {"brahman", "brahmin", "brahaman", "bhraman", "bharmn", "ब्राह्मण", "ब्राहम्ण"},
    {"bairwa", "berwa", "बैरवा"},
    {"gurjar", "gujar", "गुर्जर"},
    {"bazigar", "बाजीगर"},
    {"dhobi", "धोबी"},
    {"darzi", "दर्जी"},
    {"fakir", "फकीर"},
    {"valmiki", "balmiki", "वाल्मीकि"},
    {"chhipa", "chhippa", "छीपा"},
    {"daroga", "दरोगा"},
    {"jain", "जैन"},
    {"dangi", "डांगी"},
    {"deshwali", "देशवाली"},
    {"sindhi", "सिंधी"},
    {"arai", "अराई"},
    {"agrawal", "agarwal", "अग्रवाल"},
    {"mahajan", "महाजन"}
]



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
    is_fuzzy: bool = False
    fuzzy_target: str | None = None



def _post_process_sql(sql: str, fuzzy_target: str | None = None) -> str:
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

    # ── Step 0: Fix mismatched table aliases for columns ─────────────────────
    _COL_TO_TABLE = {}
    _MEMBER_COLS = {
        "member_name", "father_name", "mother_name", "spouse_name", "date_of_birth", "age",
        "gender", "mobile_number", "caste_category", "marital_status",
        "member_type", "relation_with_hof", "caste", "income", "occupation",
        "minority", "education", "jan_aadhaar_member_id"
    }
    _FAMILY_COLS = {
        "jan_aadhaar_number", "family_head_name", "district",
        "city", "block", "gram_panchayat", "village", "ward", "is_rural"
    }
    _BANK_COLS = {
        "bank_id", "bank_account", "bank_name", "ifsc_code", "dbt_status"
    }
    for c in _MEMBER_COLS:
        _COL_TO_TABLE[c] = "member"
    for c in _FAMILY_COLS:
        _COL_TO_TABLE[c] = "family"
    for c in _BANK_COLS:
        _COL_TO_TABLE[c] = "bank_details"

    alias_to_table = {}
    table_to_alias = {}
    for table_name in ["member", "family", "bank_details"]:
        match = re.search(rf"\b{table_name}\s+(?:AS\s+)?(\w+)\b", sql, re.IGNORECASE)
        if match:
            alias = match.group(1)
            if alias.upper() not in {"JOIN", "ON", "WHERE", "GROUP", "ORDER", "LIMIT", "SELECT", "FROM", "INNER", "LEFT", "RIGHT", "CROSS", "OUTER", "NATURAL", "AS"}:
                alias_to_table[alias.lower()] = table_name
                table_to_alias[table_name] = alias

    def prefix_replacer(match):
        alias = match.group(1)
        col = match.group(2).lower()
        owner_table = _COL_TO_TABLE.get(col)
        if owner_table:
            current_table = alias_to_table.get(alias.lower())
            if current_table != owner_table:
                correct_alias = table_to_alias.get(owner_table, owner_table)
                return f"{correct_alias}.{match.group(2)}"
        return match.group(0)

    sql = re.sub(r"\b(\w+)\.(\w+)\b", prefix_replacer, sql)

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

    # ── Step 1.0: Fuzzy Name Broadening ──────────────────────────────────────
    if fuzzy_target:
        prefix = fuzzy_target[:3]
        target_lower = fuzzy_target.lower()
        def fuzzy_repl(match):
            col_part = match.group(1)
            val = match.group(2).strip()
            from rapidfuzz.distance import JaroWinkler
            score = JaroWinkler.similarity(target_lower, val.lower())
            if score > 1.0:
                score = score / 100.0
            if score >= 0.60 or val.lower() in target_lower or target_lower in val.lower():
                return f"{col_part} LIKE '%{prefix}%'"
            return match.group(0)
        _NAME_COLS = "member_name|father_name|mother_name|spouse_name|family_head_name"
        sql = re.sub(
            rf"\b((?:\w+\.)?(?:{_NAME_COLS}))\s+LIKE\s+'%?([^'%]+)%?'",
            fuzzy_repl, sql, flags=re.IGNORECASE,
        )

    # ── Step 1.1: Caste IN Clause Expansion ──────────────────────────────────
    # Replaces IN clauses for castes with the full bilingual groups.
    def caste_in_replacer(match):
        col = match.group(1)
        in_content = match.group(2)
        vals = [v[0] or v[1] for v in re.findall(r"'([^']+)'|\"([^\"]+)\"", in_content)]
        if not vals:
            return match.group(0)
            
        all_conditions = []
        for val in vals:
            val_l = val.strip().lower()
            matched_group = False
            for group in _CASTE_GROUPS:
                if val_l in group:
                    matched_group = True
                    for term in sorted(group, key=lambda x: len(x), reverse=True):
                        formatted = term.title() if term.isascii() else term
                        all_conditions.append(f"{col} LIKE '%{formatted}%'")
                    break
            if not matched_group:
                all_conditions.append(f"{col} LIKE '%{val}%'")
                
        return "(" + " OR ".join(all_conditions) + ")"

    sql = re.sub(
        r"\b((?:\w+\.)?caste)\s+IN\s+\(([^)]+)\)",
        caste_in_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 1.2: Caste Bilingual Expansion ──────────────────────────────────

    # Expands single-language caste filters to search in both English and Hindi.
    def caste_bilingual_replacer(match):
        col = match.group(1)
        val = match.group(2).strip()
        val_l = val.lower()
        for group in _CASTE_GROUPS:
            if val_l in group:
                conditions = []
                for term in sorted(group, key=lambda x: len(x), reverse=True):
                    formatted = term.title() if term.isascii() else term
                    conditions.append(f"{col} LIKE '%{formatted}%'")
                return "(" + " OR ".join(conditions) + ")"
        return match.group(0)

    sql = re.sub(
        r"\b((?:\w+\.)?caste)\s+LIKE\s+'%?([^'%]+)%?'",
        caste_bilingual_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 1.5: Strip spurious IS NOT NULL on nullable location sub-columns ─
    # The LLM sometimes adds conditions like `f.block IS NOT NULL` or
    # `f.ward IS NOT NULL` when it JOINs the family table but has no real
    # location filter to apply. Remove these as they silently exclude families
    # that have no block/ward recorded (rural-only or urban-only families).
    _NULLABLE_LOC_COLS = r"block|ward|village|gram_panchayat|city"
    sql = re.sub(
        rf"\s+AND\s+(?:\w+\.)?(?:{_NULLABLE_LOC_COLS})\s+IS\s+NOT\s+NULL\b",
        "",
        sql, flags=re.IGNORECASE,
    )

    # ── Step 1.6: Prune redundant family JOIN ────────────────────────────────
    # The LLM sometimes joins the family table when it retrieves family_id context,
    # but does not reference any family columns in SELECT, WHERE, or other clauses.
    if "family" in sql.lower():
        family_join_pat = re.compile(
            r"\b(?:INNER\s+|LEFT\s+|RIGHT\s+|CROSS\s+)?JOIN\s+family\s*(?:\s+(?:AS\s+)?(\w+))?\s+ON\s+([\w.]+)\s*=\s*([\w.]+)",
            re.IGNORECASE
        )
        match = family_join_pat.search(sql)
        if match:
            alias = match.group(1)
            identifier = alias if alias else "family"
            start, end = match.span()
            rest_of_sql = sql[:start] + sql[end:]
            
            # Check if the identifier is referenced with a dot prefix elsewhere
            has_qualifier_ref = re.search(rf"\b{re.escape(identifier)}\.", rest_of_sql, re.IGNORECASE) is not None
            
            # Check if any non-join columns of the family table are referenced as standalone words
            _FAMILY_COLUMNS = {
                "jan_aadhaar_number", "family_head_name", "district", "city",
                "block", "gram_panchayat", "village", "ward", "is_rural"
            }
            has_column_ref = False
            for col in _FAMILY_COLUMNS:
                if re.search(rf"\b{col}\b", rest_of_sql, re.IGNORECASE):
                    has_column_ref = True
                    break
            
            if not has_qualifier_ref and not has_column_ref:
                # The join is completely unused! Strip it.
                sql = rest_of_sql
                # Clean up spacing around the removed JOIN
                sql = re.sub(r"\s+", " ", sql).strip()
                if sql.endswith("; ") or sql.endswith(";"):
                    sql = sql.rstrip("; ").rstrip(";") + ";"

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
    # Fix LIKE 'val' without wildcards (e.g. bank_name LIKE 'SBI')
    sql = re.sub(
        r"\b((?:\w+\.)?bank_name)\s*LIKE\s*'([^'%]+)'",
        lambda m: (
            m.group(0) if m.group(0).upper().startswith("UPPER(")
            else f"UPPER({m.group(1)}) LIKE '%{m.group(2).strip().upper()}%'"
        ),
        sql, flags=re.IGNORECASE,
    )

    # ── Step 2.5 (new): bank_name IN (...) → UPPER(bank_name) IN (...) ─────────────
    def bank_in_replacer(match):
        col = match.group(1)
        in_content = match.group(2)
        vals = [v[0] or v[1] for v in re.findall(r"'([^']+)'|\"([^\"]+)\"", in_content)]
        new_vals = [f"'{v.strip().upper()}'" for v in vals]
        return f"UPPER({col}) IN ({', '.join(new_vals)})"

    sql = re.sub(
        r"\b((?:\w+\.)?bank_name)\s+IN\s+\(([^)]+)\)",
        bank_in_replacer, sql, flags=re.IGNORECASE,
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

    # ── Step 3.5: Categorical IN Clause Casing Normalization ──────────────────
    def cat_in_replacer(match):
        col_raw = match.group(1)
        col = col_raw.lower()
        in_content = match.group(2)
        vals = [v[0] or v[1] for v in re.findall(r"'([^']+)'|\"([^\"]+)\"", in_content)]
        
        new_vals = []
        for val in vals:
            val_l = val.strip().lower()
            if "gender" in col:
                if val_l in ("male", "m"):
                    new_vals.append("'Male'")
                elif val_l in ("female", "f"):
                    new_vals.append("'Female'")
                else:
                    new_vals.append(f"'{val}'")
            elif "caste_category" in col:
                if val_l in ("sc", "scheduled caste", "dalit"):
                    new_vals.append("'SC'")
                elif val_l in ("st", "scheduled tribe", "tribal", "adivasi"):
                    new_vals.append("'ST'")
                elif val_l in ("obc", "other backward class", "other backward caste", "other backward", "backward class"):
                    new_vals.append("'OBC'")
                elif val_l in ("gen", "general", "general category", "open", "unreserved", "ur", "forward", "forward caste"):
                    new_vals.append("'GEN'")
                else:
                    new_vals.append(f"'{val.upper()}'")
            elif "marital_status" in col:
                if val_l in ("married",):
                    new_vals.append("'Married'")
                elif val_l in ("unmarried", "single", "never married", "bachelor", "spinster"):
                    new_vals.append("'Unmarried'")
                elif val_l in ("widow", "widowed", "widower"):
                    new_vals.append("'Widow'")
                else:
                    new_vals.append(f"'{val}'")
            else:
                new_vals.append(f"'{val}'")
                
        return f"{col_raw} IN ({', '.join(new_vals)})"

    _CAT_COLS = r"gender|caste_category|marital_status"
    sql = re.sub(
        rf"\b((?:\w+\.)?(?:{_CAT_COLS}))\s+IN\s+\(([^)]+)\)",
        cat_in_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 4 (new): Categorical LIKE → = ────────────────────────────────
    # The LLM sometimes uses LIKE for exact-match categorical columns.
    # gender, caste_category, marital_status must always use = not LIKE.
    sql = re.sub(
        r"\b((?:\w+\.)?gender)\s+LIKE\s+'%?(Male|Female)%?'",
        lambda m: f"{m.group(1)} = '{m.group(2)}'",
        sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\b((?:\w+\.)?caste_category)\s+LIKE\s+'%?(SC|ST|OBC|GEN)%?'",
        lambda m: f"{m.group(1)} = '{m.group(2).upper()}'",
        sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\b((?:\w+\.)?marital_status)\s+LIKE\s+'%?(Married|Unmarried|Widow)%?'",
        lambda m: f"{m.group(1)} = '{m.group(2)}'",
        sql, flags=re.IGNORECASE,
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
        r"\b((?:\w+\.)?is_rural)\s*(?:=|LIKE)\s*['\"]?(\w+)['\"]?",
        rural_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 6: District casing normalisation (known districts only) ────────
    def district_exact_replacer(match: re.Match[str]) -> str:
        col = match.group(1)
        val = match.group(2).strip().lower()
        canonical = _DISTRICT_CANONICAL.get(val)   # O(1) dict lookup
        if canonical:
            return f"{col} = '{canonical}'"
        # Not a known district — Step 9 will redirect it
        return match.group(0)

    sql = re.sub(
        r"\b((?:\w+\.)?district)\s*=\s*'([^']+)'",
        district_exact_replacer, sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r'\b((?:\w+\.)?district)\s*=\s*"([^"]+)"',
        district_exact_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 8 (new): District LIKE → = for known districts ──────────────
    # Convert "district LIKE '%Jaipur%'" → "district = 'Jaipur'" when the
    # stripped value is a known district, preventing partial-match false positives.
    def district_like_replacer(match: re.Match[str]) -> str:
        col = match.group(1)
        val = match.group(2).strip()
        canonical = _DISTRICT_CANONICAL.get(val.lower())
        if canonical:
            return f"{col} = '{canonical}'"
        return match.group(0)

    sql = re.sub(
        r"\b((?:\w+\.)?district)\s+LIKE\s+'%?([^'%]+?)%?'",
        district_like_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 8.5: Redirect district IN clauses containing non-district values ─
    def district_in_replacer(match: re.Match[str]) -> str:
        col = match.group(1)
        in_content = match.group(2)
        prefix = col.split('.')[0] + "." if '.' in col else ""
        
        vals = [v[0] or v[1] for v in re.findall(r"'([^']+)'|\"([^\"]+)\"", in_content)]
        if not vals:
            return match.group(0)
            
        has_non_district = any(v.lower() not in _DISTRICTS_LOWER for v in vals)
        
        if has_non_district:
            conditions = []
            for val in vals:
                val_l = val.strip().lower()
                if val_l in _DISTRICTS_LOWER:
                    canonical = _DISTRICT_CANONICAL[val_l]
                    conditions.append(f"{col} = '{canonical}'")
                else:
                    conditions.append(f"({prefix}block LIKE '%{val}%' OR {prefix}village LIKE '%{val}%')")
            return "(" + " OR ".join(conditions) + ")"
        else:
            new_vals = [f"'{_DISTRICT_CANONICAL[v.lower()]}'" for v in vals]
            return f"{col} IN ({', '.join(new_vals)})"

    sql = re.sub(
        r"\b((?:\w+\.)?district)\s+IN\s+\(([^)]+)\)",
        district_in_replacer, sql, flags=re.IGNORECASE,
    )

    # ── Step 9: Redirect district → block/village for non-district locations ──
    # (previously Step 7 — now uses module-level _DISTRICTS_LOWER)
    redirect_pattern = (
        r"\b((?:[A-Za-z_]\w*\.)?)"
        r"district\s*(?:=\s*'([^']+)'|LIKE\s*'%([^'%]+)%')"
    )

    def district_redirect_full(match: re.Match[str]) -> str:
        prefix = match.group(1) or ""
        val = (match.group(2) or match.group(3) or "").strip()
        if not val or val.lower() in _DISTRICTS_LOWER:
            return match.group(0)
        return f"({prefix}block LIKE '%{val}%' OR {prefix}village LIKE '%{val}%')"

    sql = re.sub(redirect_pattern, district_redirect_full, sql, flags=re.IGNORECASE)

    # ── Steps 10-15 (new): Family member count post-processing ───────────────

    # Step 10: COUNT(member.member_id) → COUNT(*)
    sql = re.sub(
        r"COUNT\s*\(\s*member\.member_id\s*\)",
        "COUNT(*)",
        sql, flags=re.IGNORECASE,
    )

    # Step 11: Fix broken AVG subquery alias (e.g. AVG(T2.member_count) when alias is T1).
    # Detects the actual subquery alias from the AS clause and substitutes it.
    def fix_avg_alias(sql_str: str) -> str:
        inner_match = re.search(r'\)\s+AS\s+(\w+)\s*$', sql_str.rstrip(';'), re.IGNORECASE)
        if inner_match:
            correct_alias = inner_match.group(1)
            sql_str = re.sub(
                r'AVG\s*\(\s*(\w+)\.member_count\s*\)',
                lambda m: (
                    f"AVG({correct_alias}.member_count)"
                    if m.group(1).lower() != correct_alias.lower()
                    else m.group(0)
                ),
                sql_str, flags=re.IGNORECASE,
            )
        return sql_str

    sql = fix_avg_alias(sql)

    # Step 12: Rename misleading 'family_count' alias → 'member_count'
    sql = re.sub(
        r"COUNT\(\*\)\s+AS\s+family_count",
        "COUNT(*) AS member_count",
        sql, flags=re.IGNORECASE,
    )

    # Step 13 and Step 14 removed: family count queries now use only the member
    # table (GROUP BY member.family_id) so family_id in SELECT is correct.
    # No JOIN to family table means family_head_name is not available to substitute.

    # Step 15: Remove unnecessary 'AS display_column' alias
    sql = re.sub(
        r"\b(\w+\.family_head_name)\s+AS\s+display_column\b",
        r"\1",
        sql, flags=re.IGNORECASE,
    )

    # ── Step 16: Normalize bank account number column names ───────────────────
    sql = re.sub(r"\bbank_account_number\b", "bank_account", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bbank_account_no\b", "bank_account", sql, flags=re.IGNORECASE)

    # ── Step 17: Clean up trailing commentary/notes ──────────────────────────
    if ";" in sql:
        parts = sql.split(";", 1)
        sql = parts[0].strip() + ";"

    # ── Step 18: Transitively inject family/member JOINs if referenced but missing ──
    member_alias = table_to_alias.get("member", "member")
    family_alias = table_to_alias.get("family")
    has_family_ref = re.search(r"\b(?:family|f)\.\w+\b", sql, re.IGNORECASE) is not None
    has_family_join = re.search(r"\b(?:JOIN|FROM)\s+family\b", sql, re.IGNORECASE) is not None
    if has_family_ref and not has_family_join:
        f_alias = family_alias if family_alias else "f"
        join_str = f" JOIN family {f_alias} ON {member_alias}.family_id = {f_alias}.family_id"
        where_match = re.search(r"\b(WHERE|GROUP\s+BY|ORDER\s+BY|LIMIT)\b", sql, re.IGNORECASE)
        if where_match:
            start = where_match.start()
            sql = sql[:start] + join_str + " " + sql[start:]
            table_to_alias["family"] = f_alias
            alias_to_table[f_alias.lower()] = "family"
        else:
            sql = sql.rstrip(";") + join_str + ";"

    has_member_ref = re.search(r"\b(?:member|m)\.\w+\b", sql, re.IGNORECASE) is not None
    has_member_join = re.search(r"\b(?:JOIN|FROM)\s+member\b", sql, re.IGNORECASE) is not None
    if has_member_ref and not has_member_join:
        m_alias = member_alias if member_alias else "m"
        if "family" in sql.lower():
            f_alias = table_to_alias.get("family", "family")
            join_str = f" JOIN member {m_alias} ON {m_alias}.family_id = {f_alias}.family_id"
        elif "bank_details" in sql.lower():
            b_alias = table_to_alias.get("bank_details", "bank_details")
            join_str = f" JOIN member {m_alias} ON {b_alias}.member_id = {m_alias}.member_id"
        else:
            join_str = ""
        if join_str:
            where_match = re.search(r"\b(WHERE|GROUP\s+BY|ORDER\s+BY|LIMIT)\b", sql, re.IGNORECASE)
            if where_match:
                start = where_match.start()
                sql = sql[:start] + join_str + " " + sql[start:]
                table_to_alias["member"] = m_alias
                alias_to_table[m_alias.lower()] = "member"
            else:
                sql = sql.rstrip(";") + join_str + ";"

    # ── Step 19: Re-run prefix correction to handle any injected tables ───────
    alias_to_table.clear()
    table_to_alias.clear()
    for table_name in ["member", "family", "bank_details"]:
        match = re.search(rf"\b{table_name}\s+(?:AS\s+)?(\w+)\b", sql, re.IGNORECASE)
        if match:
            alias = match.group(1)
            if alias.upper() not in {"JOIN", "ON", "WHERE", "GROUP", "ORDER", "LIMIT", "SELECT", "FROM", "INNER", "LEFT", "RIGHT", "CROSS", "OUTER", "NATURAL", "AS"}:
                alias_to_table[alias.lower()] = table_name
                table_to_alias[table_name] = alias

    sql = re.sub(r"\b(\w+)\.(\w+)\b", prefix_replacer, sql)

    return sql


def _fix_no_bank_sql(sql: str, question: str) -> str:
    """
    Post-process SQL for "no bank account" / unbanked queries.
    Ensures LEFT JOIN is used (not INNER JOIN / bare JOIN) and that
    bank_details.bank_id IS NULL is included in the WHERE clause.
    Called immediately after _post_process_sql in the generation loop.
    """
    import re

    if not any(w in question.lower() for w in _NO_BANK_WORDS):
        return sql

    # ── Step 1: Inject bank_details LEFT JOIN if LLM omitted it entirely ─────
    if "bank_details" not in sql.lower():
        # BUG FIX: use a keyword-aware negative lookahead so SQL keywords like
        # JOIN/WHERE/ON are not consumed as a table alias by the optional alias group.
        _KW = r"(?!(?:JOIN|WHERE|ON|LEFT|RIGHT|INNER|OUTER|GROUP|ORDER|HAVING|LIMIT|SELECT|FROM)\b)"
        sql = re.sub(
            rf"\b(FROM\s+member(?:\s+(?:AS\s+)?{_KW}\w+)?)\b",
            r"\1 LEFT JOIN bank_details ON bank_details.member_id = member.member_id",
            sql, flags=re.IGNORECASE, count=1,
        )

    # ── Step 2: Normalise all bank_details JOINs to LEFT JOIN ────────────────
    # First promote INNER JOIN → LEFT JOIN explicitly.
    sql = re.sub(
        r"\bINNER\s+JOIN\s+bank_details\b",
        "LEFT JOIN bank_details",
        sql, flags=re.IGNORECASE,
    )
    # Replace any remaining bare/FULL/CROSS JOIN bank_details with LEFT JOIN.
    # Then clean up double qualifiers (e.g. "LEFT LEFT JOIN").
    sql = re.sub(r"\bJOIN\s+bank_details\b", "LEFT JOIN bank_details", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bLEFT\s+LEFT\s+JOIN\b",  "LEFT JOIN",  sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bRIGHT\s+LEFT\s+JOIN\b", "RIGHT JOIN", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bFULL\s+LEFT\s+JOIN\b",  "FULL JOIN",  sql, flags=re.IGNORECASE)

    # ── Step 3: Add IS NULL check if missing ─────────────────────────────────
    if "bank_details" in sql.lower() and "IS NULL" not in sql.upper():
        if re.search(r"\bWHERE\b", sql, re.IGNORECASE):
            sql = re.sub(
                r"\bWHERE\b",
                "WHERE bank_details.bank_id IS NULL AND",
                sql, flags=re.IGNORECASE, count=1,
            )
        else:
            # Try to insert before GROUP BY / ORDER BY / LIMIT
            injected = re.sub(
                r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT)\b",
                r"WHERE bank_details.bank_id IS NULL \1",
                sql, flags=re.IGNORECASE, count=1,
            )
            if injected == sql:          # no clause found — append to end
                sql = sql.rstrip(";") + " WHERE bank_details.bank_id IS NULL;"
            else:
                sql = injected

    # ── Step 4: Strip spurious member_type = 'MEM' the LLM adds ─────────────
    if not any(w in question.lower() for w in _MEMBER_TYPE_WORDS):
        sql = re.sub(
            r"\s+AND\s+(?:\w+\.)?member_type\s*=\s*'MEM'",
            "",
            sql, flags=re.IGNORECASE,
        )

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

    # Fuzzy intent detection
    from normalization.fuzzy_match import is_fuzzy_intent, extract_fuzzy_target
    is_fuzzy = is_fuzzy_intent(question)
    fuzzy_target = None
    if is_fuzzy:
        target = extract_fuzzy_target(question)
        if target and len(target) >= 3:
            fuzzy_target = target
        else:
            is_fuzzy = False

    previous_error: str | None = None
    sql = ""
    validation_errors: list[str] = []
    final_sql_is_valid = False
    for _ in range(settings.max_retries):
        prompt = prompt_builder.build(retrieval, previous_error=previous_error)
        sql = generator.generate(prompt)
        sql = _post_process_sql(sql, fuzzy_target=fuzzy_target)
        sql = _fix_no_bank_sql(sql, question)   # handles unbanked / no-account queries
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
        is_fuzzy=is_fuzzy,
        fuzzy_target=fuzzy_target,
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
        import_excel_dataset("dummy_dataset/Dummy_Data_Set.xlsx")
        print(f"Demo database ready at {settings.sqlite_path} loaded from Dummy_Data_Set.xlsx")
    if args.import_excel:
        report = import_excel_dataset(args.import_excel)
        print(
            f"Imported {report.members_loaded} members, {report.families_loaded} family records, "
            f"and {report.bank_records_loaded} bank records from {report.source_name}."
        )

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
        preview = execute_select_preview(
            output.sql,
            max_rows=20,
            fuzzy_target=output.fuzzy_target,
            is_fuzzy=output.is_fuzzy,
        )
        if output.is_fuzzy:
            print(f"\nSimilarity matches for '{output.fuzzy_target}' (Jaro-Winkler >= 0.80)")
        else:
            print("\nMatching entries")
        print(preview.rows.to_string(index=False) if not preview.rows.empty else "No matching entries.")
        if preview.truncated:
            if output.is_fuzzy:
                print("Showing the first 20 similarity matches only.")
            else:
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
