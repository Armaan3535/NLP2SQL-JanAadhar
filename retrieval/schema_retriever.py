from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.settings import settings
from database.schema_metadata import COLUMNS, RAJASTHAN_DISTRICTS_41, RELATIONSHIPS, TABLES
from embeddings.faiss_store import FaissSchemaStore


# Terms that signal the user wants the detailed caste name (member.caste)
CASTE_DETAIL_TERMS = {"caste", "community", "jati"}
# Terms that signal the user wants the caste category SC/ST/OBC/GEN (member.caste_category)
CASTE_CATEGORY_TERMS = {"category", "sc", "st", "obc", "general", "gen", "scheduled",
                        "backward", "forward", "unreserved", "open category"}
# Combined for backward-compat where either column is relevant
CASTE_TERMS = CASTE_DETAIL_TERMS | CASTE_CATEGORY_TERMS

WELFARE_TERMS = {"pension", "beneficiary", "beneficiaries", "benefit", "scheme", "nfsa", "bpl", "apl", "ration"}
BANK_TERMS = {
    "bank", "account", "ifsc", "dbt", "payment",
    # Common bank abbreviations used in queries
    "sbi", "pnb", "bob", "hdfc", "icici", "uco", "canara", "baroda",
    "gramin", "cooperative", "union bank", "central bank", "indian bank",
}
IDENTITY_TERMS = {"aadhaar", "jan", "voter", "pan", "identity", "id", "mobile", "phone", "email", "photo"}
DISABILITY_TERMS = {"disabled", "disability", "divyang"}
RELIGION_TERMS = {"religion", "faith"}
MINORITY_TERMS = {"minority", "muslim", "muslims", "jain", "jains"}
EDUCATION_TERMS = {"education", "qualification", "illiterate", "literate", "graduate", "school", "pass", "matric", "intermediate"}
RURAL_TERMS = {"rural", "urban", "city dweller", "village people", "village families", "city families"}

KNOWN_CASTES = {
    "jat", "arai", "fakir", "mina", "ramgadiya", "rajput", "rajpoot", "moyla", 
    "gauswami", "deshwali", "chhipa", "chhipi", "kandera", "jain", "brahman", 
    "brahmin", "gurjar", "gujar", "pathan", "valmiki", "balmiki", "berwa", 
    "bairwa", "mehtar", "bazigar", "dangi", "sidh", "dhobi", "darzi", "daroga", 
    "sindhi", "vaishya", "pinjara", "जाट", "राजपूत", "मीना", "महाजन", "बाजीगर",
    "अग्रवाल", "ब्राह्मण", "ब्राहम्ण", "sc", "st", "obc", "caste", "community"
}
RAJASTHAN_DISTRICT_TERMS = {
    term
    for district in RAJASTHAN_DISTRICTS_41
    for term in district.lower().replace("-", " ").split()
}
GEOGRAPHY_TERMS = RAJASTHAN_DISTRICT_TERMS | {
    "district",
    "zilla",
    "block",
    "village",
    "ward",
    "panchayat",
}
DISTRICT_TERMS = RAJASTHAN_DISTRICT_TERMS | {"district", "zilla", "city", "location"}
LOCATION_PREPOSITIONS = {"in", "from", "at"}
LOCATION_STOPWORDS = {
    "age",
    "years",
    "male",
    "female",
    "boys",
    "girls",
    "beneficiaries",
    "beneficiary",
    "pension",
    "scheme",
    "nfsa",
    "ekyc",
    "active",
    "pending",
}


@dataclass
class RetrievalResult:
    question: str
    tables: list[str]
    columns: list[str]
    relationships: list[dict[str, str]]
    documents: list[dict[str, Any]]
    confidence: float


class SchemaRetriever:
    def __init__(self, store: FaissSchemaStore | None = None):
        self.store = store or FaissSchemaStore()

    def retrieve(self, question: str, top_k: int = settings.retrieval_top_k) -> RetrievalResult:
        docs = self.store.search(question, top_k=top_k)
        tables: set[str] = set()
        columns: set[str] = set()
        question_lower = question.lower()
        question_terms = _terms(question_lower)
        lexical_columns: set[str] = set()
        semantic_columns: set[str] = set()

        for table in TABLES:
            if _matches(table.table, question_lower, question_terms) or any(_matches(alias, question_lower, question_terms) for alias in table.aliases):
                tables.add(table.table)

        for column in COLUMNS:
            lexical_terms = [column.column.replace("_", " "), *column.aliases, *column.sample_values]
            if any(term and _matches(term, question_lower, question_terms) for term in lexical_terms):
                lexical_columns.add(column.qualified_name)

        # Add lexical columns first
        columns.update(lexical_columns)

        # Add top semantic columns that are not already present, up to a limit of 6
        semantic_added = 0
        for doc in docs:
            if doc.get("kind") != "column" or not doc.get("qualified_name"):
                continue
            qualified_name = doc["qualified_name"]
            if qualified_name in columns:
                continue
            if _column_allowed_by_domain(qualified_name, question_lower, question_terms):
                columns.add(qualified_name)
                semantic_added += 1
            if semantic_added >= 6:
                break

        non_district_loc = False
        if _mentions_possible_location(question_lower):
            known_districts = {d.lower() for d in RAJASTHAN_DISTRICTS_41}
            if not (question_terms & known_districts):
                non_district_loc = True

        if (GEOGRAPHY_TERMS & question_terms) or _mentions_possible_location(question_lower):
            tables.add("family")
            columns.add("family.family_id")
            columns.add("family.district")
            if {"block", "tehsil", "kotputli"} & question_terms or non_district_loc:
                columns.add("family.block")
            if "village" in question_lower or non_district_loc:
                columns.add("family.village")

        # is_rural: include when question mentions rural/urban classification
        if RURAL_TERMS & question_terms or any(t in question_lower for t in ("rural", "urban", "is_rural")):
            tables.add("family")
            columns.add("family.is_rural")

        # Force retrieve member.caste if query contains any known caste terms
        if (KNOWN_CASTES & question_terms) or any(caste in question_lower for caste in KNOWN_CASTES):
            columns.add("member.caste")

        tables.update(column.split(".")[0] for column in columns)

        # Include join keys and display fields for tables already selected, without broadening the prompt too much.
        for relationship in RELATIONSHIPS:
            if relationship["from_table"] in tables and relationship["to_table"] in tables:
                columns.add(f'{relationship["from_table"]}.{relationship["from_column"]}')
                columns.add(f'{relationship["to_table"]}.{relationship["to_column"]}')

        if any(token in question.lower() for token in ["show", "list", "display", "beneficiary", "all"]):
            for candidate in ["member.member_name", "family.jan_aadhaar_number"]:
                table, column = candidate.split(".")
                if table in tables and any(c.table == table and c.column == column for c in COLUMNS):
                    columns.add(candidate)

        columns = _prune_columns(columns, question_lower, question_terms)
        tables = {column.split(".")[0] for column in columns}
        relationships = [
            relationship
            for relationship in RELATIONSHIPS
            if relationship["from_table"] in tables and relationship["to_table"] in tables
        ]
        confidence = sum(doc["score"] for doc in docs[: min(5, len(docs))]) / max(1, min(5, len(docs)))
        return RetrievalResult(
            question=question,
            tables=sorted(tables),
            columns=sorted(columns),
            relationships=relationships,
            documents=docs,
            confidence=round(confidence, 4),
        )


def _terms(text: str) -> set[str]:
    import re

    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def _matches(term: str, question_lower: str, question_terms: set[str]) -> bool:
    normalized = term.lower().strip()
    if not normalized:
        return False
    if " " in normalized:
        return normalized in question_lower
    return normalized in question_terms


def _column_allowed_by_domain(qualified_name: str, question_lower: str, question_terms: set[str]) -> bool:
    table, column = qualified_name.split(".")
    # bank_details: only include when question mentions banking/payment terms
    if table == "bank_details" and not (BANK_TERMS & question_terms):
        return False
    # caste_category (SC/ST/OBC/GEN) only when user explicitly mentions a category term
    # NOTE: the word 'caste' alone should NOT trigger caste_category retrieval —
    # it only means the user wants the caste name (member.caste).
    if qualified_name == "member.caste_category" and not (CASTE_CATEGORY_TERMS & question_terms):
        return False
    if qualified_name == "member.minority" and not (MINORITY_TERMS & question_terms):
        return False
    if qualified_name == "member.education" and not (EDUCATION_TERMS & question_terms):
        return False
    return True


def _prune_columns(columns: set[str], question_lower: str, question_terms: set[str]) -> set[str]:
    pruned: set[str] = set()
    possible_location = _mentions_possible_location(question_lower)

    non_district_loc = False
    if possible_location:
        known_districts = {d.lower() for d in RAJASTHAN_DISTRICTS_41}
        if not (question_terms & known_districts):
            non_district_loc = True

    for qualified_name in columns:
        table, column = qualified_name.split(".")
        if not _column_allowed_by_domain(qualified_name, question_lower, question_terms):
            continue
        if table == "bank_details" and not (BANK_TERMS & question_terms):
            continue
        if qualified_name in {
            "member.jan_aadhaar_member_id",
            "member.mobile_number",
        } and not (IDENTITY_TERMS & question_terms):
            continue
        if qualified_name in {"family.jan_aadhaar_number"} and not ((IDENTITY_TERMS | WELFARE_TERMS) & question_terms):
            continue
        if qualified_name == "family.block" and not ({"block", "tehsil", "kotputli"} & question_terms or non_district_loc):
            continue
        if qualified_name == "family.gram_panchayat" and not {"gram", "panchayat", "gp"} & question_terms:
            continue
        if qualified_name == "family.village" and not ("village" in question_terms or non_district_loc):
            continue
        if qualified_name == "family.ward" and "ward" not in question_terms:
            continue
        if qualified_name == "family.city" and not {"city", "town", "urban"} & question_terms:
            continue
        if qualified_name == "family.district" and not ((DISTRICT_TERMS | GEOGRAPHY_TERMS) & question_terms or possible_location):
            continue
        if qualified_name == "family.is_rural" and not (RURAL_TERMS & question_terms or any(t in question_lower for t in ("rural", "urban", "is_rural"))):
            continue
        pruned.add(qualified_name)
    return pruned


def _mentions_possible_location(question_lower: str) -> bool:
    import re

    for preposition in LOCATION_PREPOSITIONS:
        match = re.search(rf"\b{preposition}\s+([a-zA-Z][a-zA-Z-]*)\b", question_lower)
        if not match:
            continue
        candidate = match.group(1).lower()
        if candidate not in LOCATION_STOPWORDS and not candidate.isdigit():
            return True
    return False
