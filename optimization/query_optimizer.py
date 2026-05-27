from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text

from database.connection import get_engine
from database.schema_metadata import COLUMNS
from validation.sql_validator import SQLValidator


@dataclass
class OptimizationReport:
    execution_plan: list[str]
    execution_time_ms: float
    index_recommendations: list[str]


class QueryOptimizer:
    def __init__(self, database_url: str | None = None):
        self.engine = get_engine(database_url)
        self.validator = SQLValidator()

    def explain(self, sql: str) -> list[str]:
        validation = self.validator.validate(sql)
        if not validation.valid:
            raise ValueError(f"Refusing to explain unsafe SQL: {'; '.join(validation.errors)}")
        with self.engine.connect() as connection:
            rows = connection.execute(text(f"EXPLAIN QUERY PLAN {sql.rstrip(';')}")).fetchall()
        return [" | ".join(str(part) for part in row) for row in rows]

    def profile(self, sql: str, run_query: bool = False) -> OptimizationReport:
        start = time.perf_counter()
        plan = self.explain(sql)
        if run_query:
            validation = self.validator.validate(sql)
            if not validation.valid:
                raise ValueError(f"Refusing to execute unsafe SQL: {'; '.join(validation.errors)}")
            with self.engine.connect() as connection:
                connection.execute(text(sql)).fetchmany(10)
        elapsed = (time.perf_counter() - start) * 1000
        return OptimizationReport(plan, round(elapsed, 2), self.recommend_indexes(sql))

    def recommend_indexes(self, sql: str) -> list[str]:
        lowered = sql.lower()
        recommendations: list[str] = []
        for column in COLUMNS:
            if f"{column.table}.{column.column}".lower() in lowered or f" {column.column.lower()} " in lowered:
                if not column.indexed:
                    recommendations.append(f"Consider index on {column.table}({column.column}) if this predicate is frequent.")
        return recommendations
