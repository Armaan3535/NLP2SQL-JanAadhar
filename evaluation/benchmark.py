from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from app import generate_sql_pipeline
from validation.sql_validator import SQLValidator


@dataclass
class BenchmarkCase:
    question: str
    expected_sql: str


@dataclass
class BenchmarkResult:
    question: str
    generated_sql: str
    expected_sql: str
    exact_match: bool
    schema_accuracy: bool
    retrieval_accuracy: float
    latency_ms: float


def normalize(sql: str) -> str:
    return " ".join(sql.lower().strip().rstrip(";").split())


def run_benchmark(path: str = "evaluation/benchmark_cases.json") -> list[BenchmarkResult]:
    cases = [BenchmarkCase(**item) for item in json.loads(Path(path).read_text(encoding="utf-8"))]
    validator = SQLValidator()
    results: list[BenchmarkResult] = []
    for case in cases:
        start = time.perf_counter()
        output = generate_sql_pipeline(case.question, ask_model_pull=False)
        elapsed = (time.perf_counter() - start) * 1000
        validation = validator.validate(output.sql)
        expected_terms = {token for token in normalize(case.expected_sql).split() if "." in token}
        generated_terms = set(output.retrieved_columns)
        retrieval_accuracy = len(expected_terms & generated_terms) / max(1, len(expected_terms))
        results.append(
            BenchmarkResult(
                question=case.question,
                generated_sql=output.sql,
                expected_sql=case.expected_sql,
                exact_match=normalize(output.sql) == normalize(case.expected_sql),
                schema_accuracy=validation.valid,
                retrieval_accuracy=round(retrieval_accuracy, 4),
                latency_ms=round(elapsed, 2),
            )
        )
    return results


if __name__ == "__main__":
    for result in run_benchmark():
        print(json.dumps(asdict(result), indent=2))
