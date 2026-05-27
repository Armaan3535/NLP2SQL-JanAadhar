from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlparse

from database.schema_metadata import RELATIONSHIPS, all_table_names, columns_by_table


DISALLOWED = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "merge",
    "grant",
    "revoke",
    "vacuum",
    "attach",
    "detach",
    "pragma",
    "analyze",
    "reindex",
    "into",
}
SQL_KEYWORDS = {
    "select", "from", "where", "join", "on", "and", "or", "group", "by", "order",
    "limit", "count", "as", "desc", "asc", "having", "distinct", "top",
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


class SQLValidator:
    def __init__(self):
        self.tables = all_table_names()
        self.columns = columns_by_table()

    def validate(self, sql: str, allowed_tables: list[str] | None = None, allowed_columns: list[str] | None = None) -> ValidationResult:
        errors: list[str] = []
        raw_sql = sql.strip()
        
        # Mask string literals in single or double quotes to prevent false-positives for multi-word literals
        masked_sql = re.sub(r"'(?:''|[^'])*'", "'__LITERAL__'", raw_sql)
        masked_sql = re.sub(r'"(?:""|[^"])*"', '"__LITERAL__"', masked_sql)
        
        parsed = [statement for statement in sqlparse.parse(masked_sql) if str(statement).strip().strip(";")]
        if not parsed:
            return ValidationResult(False, ["SQL could not be parsed."])
        if len(parsed) != 1:
            errors.append("Only one SQL statement is allowed.")
        normalized = str(parsed[0]).strip().rstrip(";")
        alias_map = self._extract_aliases(normalized)
        first_token = parsed[0].token_first(skip_cm=True)
        if not first_token or first_token.value.lower() != "select":
            errors.append("Only SELECT statements are allowed.")
        if re.search(r";\s*\S", raw_sql.rstrip(";")):
            errors.append("Only one SQL statement is allowed.")
        lower = normalized.lower()
        if any(re.search(rf"\b{word}\b", lower) for word in DISALLOWED):
            errors.append("Statement contains a disallowed write or DDL keyword.")

        referenced_tables = self._extract_tables(normalized)
        unknown_tables = referenced_tables - self.tables
        if unknown_tables:
            errors.append(f"Unknown tables: {', '.join(sorted(unknown_tables))}.")
        if allowed_tables:
            outside_context = referenced_tables - set(allowed_tables)
            if outside_context:
                errors.append(f"Tables outside retrieved context: {', '.join(sorted(outside_context))}.")

        unknown_columns = self._unknown_columns(normalized, referenced_tables, alias_map)
        if unknown_columns:
            errors.append(f"Unknown columns: {', '.join(sorted(unknown_columns))}.")
        missing_column_tables = self._qualified_column_tables_not_in_from(normalized, referenced_tables, alias_map)
        if missing_column_tables:
            errors.append(f"Qualified column references tables not present in FROM/JOIN: {', '.join(sorted(missing_column_tables))}.")
        if allowed_columns:
            context_columns = set(allowed_columns)
            qualified_refs = set(re.findall(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b", normalized))
            outside_columns = {
                f"{alias_map.get(table, table)}.{column}"
                for table, column in qualified_refs
            } - context_columns
            # Normalize and filter outside columns to be robust to casing, bypassing core member/family tables
            outside_columns = {
                col for col in outside_columns 
                if col.split(".")[0].lower() in {t.lower() for t in referenced_tables} 
                and col.split(".")[0].lower() not in {"member", "family"}
            }
            if outside_columns:
                errors.append(f"Columns outside retrieved context: {', '.join(sorted(outside_columns))}.")

        join_errors = self._validate_joins(normalized, alias_map)
        errors.extend(join_errors)

        # Verbose terminal logging to help identify any issues under Streamlit or CLI runs
        print(f"[SQLValidator DEBUG] sql: {sql}")
        print(f"[SQLValidator DEBUG] referenced_tables: {referenced_tables}")
        print(f"[SQLValidator DEBUG] allowed_columns: {allowed_columns}")
        print(f"[SQLValidator DEBUG] validation result errors: {errors}")

        return ValidationResult(valid=not errors, errors=errors)

    def _extract_aliases(self, sql: str) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for table, alias in re.findall(
            r"\b(?:from|join)\s+([a-zA-Z_][\w]*)(?:\s+(?:as\s+)?([a-zA-Z_][\w]*))?",
            sql,
            flags=re.IGNORECASE,
        ):
            if table in self.tables and alias and alias.lower() not in SQL_KEYWORDS:
                aliases[alias] = table
            if table in self.tables:
                aliases[table] = table
        return aliases

    def _extract_tables(self, sql: str) -> set[str]:
        names = set()
        for match in re.finditer(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", sql, flags=re.IGNORECASE):
            names.add(match.group(1))
        return names

    def _unknown_columns(self, sql: str, referenced_tables: set[str], alias_map: dict[str, str]) -> set[str]:
        unknown: set[str] = set()
        for table, column in re.findall(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b", sql):
            resolved_table = alias_map.get(table, table)
            if resolved_table in self.tables and column not in self.columns.get(resolved_table, set()):
                unknown.add(f"{resolved_table}.{column}")
        if len(referenced_tables) == 1:
            table = next(iter(referenced_tables))
            known = self.columns.get(table, set())
            for identifier in re.findall(r"\b([a-zA-Z_][\w]*)\b", sql):
                lowered = identifier.lower()
                if identifier.startswith("__") or lowered == "__literal__":
                    continue
                if lowered in SQL_KEYWORDS or identifier in self.tables or identifier.isdigit():
                    continue
                if identifier.upper() == identifier and len(identifier) <= 8:
                    continue
                if identifier not in known and not re.search(rf"\b(?:from|join|as)\s+{identifier}\b", sql, re.IGNORECASE):
                    # Skip string-like values handled by SQL tokenizer poorly in this lightweight path.
                    if f"'{identifier}'" not in sql and f'"{identifier}"' not in sql:
                        unknown.add(identifier)
        return unknown
        return unknown

    def _qualified_column_tables_not_in_from(self, sql: str, referenced_tables: set[str], alias_map: dict[str, str]) -> set[str]:
        missing: set[str] = set()
        for table_or_alias, _column in re.findall(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b", sql):
            resolved_table = alias_map.get(table_or_alias, table_or_alias)
            if resolved_table in self.tables and resolved_table not in referenced_tables:
                missing.add(resolved_table)
        return missing

    def _validate_joins(self, sql: str, alias_map: dict[str, str]) -> list[str]:
        allowed_pairs = {
            frozenset({f"{r['from_table']}.{r['from_column']}", f"{r['to_table']}.{r['to_column']}"})
            for r in RELATIONSHIPS
        }
        errors: list[str] = []
        for left_table, left_col, right_table, right_col in re.findall(
            r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\s*=\s*([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b",
            sql,
        ):
            resolved_left = alias_map.get(left_table, left_table)
            resolved_right = alias_map.get(right_table, right_table)
            pair = frozenset({f"{resolved_left}.{left_col}", f"{resolved_right}.{right_col}"})
            if resolved_left != resolved_right and pair not in allowed_pairs:
                errors.append(f"Join is not a declared relationship: {resolved_left}.{left_col} = {resolved_right}.{right_col}.")
        return errors
