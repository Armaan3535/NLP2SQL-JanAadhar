from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text

from database.connection import get_engine
from validation.sql_validator import SQLValidator


@dataclass(frozen=True)
class QueryResultPreview:
    rows: pd.DataFrame
    truncated: bool
    displayed_rows: int


def execute_select_preview(sql: str, max_rows: int = 200, database_url: str | None = None) -> QueryResultPreview:
    validation = SQLValidator().validate(sql)
    if not validation.valid:
        raise ValueError(f"Refusing to execute unsafe SQL: {'; '.join(validation.errors)}")
    safe_sql = sql.strip().rstrip(";")
    limited_sql = f"SELECT * FROM ({safe_sql}) AS generated_result LIMIT {max_rows + 1}"
    with get_engine(database_url).connect() as connection:
        result = connection.execute(text(limited_sql))
        columns = list(result.keys())
        records = result.fetchall()
    truncated = len(records) > max_rows
    visible_records = records[:max_rows]
    frame = pd.DataFrame(visible_records, columns=columns)
    return QueryResultPreview(rows=frame, truncated=truncated, displayed_rows=len(frame))
