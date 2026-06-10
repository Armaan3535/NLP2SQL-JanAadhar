from __future__ import annotations

import pandas as pd

from normalization.fuzzy_match import is_fuzzy_intent, extract_fuzzy_target, fuzzy_rerank


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_df(names: list[str]) -> pd.DataFrame:
    """Build a minimal member_name DataFrame for rerank tests."""
    return pd.DataFrame({"member_name": names, "age": range(len(names))})


# ── Intent detection ──────────────────────────────────────────────────────────

def test_is_fuzzy_intent_detects_all_trigger_phrases():
    triggers = [
        "show names similar to X",
        "find members whose name is like X",
        "show names that sound like X",
        "members spelled like X",
        "do a fuzzy search for X",
        "find approximate matches for X",
        "show members resembling X",
    ]
    for phrase in triggers:
        assert is_fuzzy_intent(phrase) is True, f"Should detect fuzzy intent: {phrase!r}"


def test_is_fuzzy_intent_rejects_non_fuzzy_queries():
    non_fuzzy = [
        "show all members in jaipur",
        "how many families have income > 50000",
        "list female members from ajmer",
        "count members with bank account",
    ]
    for phrase in non_fuzzy:
        assert is_fuzzy_intent(phrase) is False, f"Should NOT detect fuzzy intent: {phrase!r}"


# ── Target extraction ─────────────────────────────────────────────────────────

def test_extract_fuzzy_target_stops_at_location_prepositions():
    # "in", "from" are stop words — target should end before them
    assert extract_fuzzy_target("similar to Abc in jaipur") == "Abc"
    assert extract_fuzzy_target("name like Xyz from ajmer") == "Xyz"


def test_extract_fuzzy_target_captures_multi_word_names():
    # Multi-word targets should be fully captured until a stop word
    result = extract_fuzzy_target("similar to Foo Bar Baz")
    assert result == "Foo Bar Baz"


def test_extract_fuzzy_target_returns_title_case():
    # Output must always be Title Case regardless of input casing
    result = extract_fuzzy_target("similar to foo bar")
    assert result == result.title()


def test_extract_fuzzy_target_returns_none_for_non_fuzzy():
    assert extract_fuzzy_target("show all members in jaipur") is None


# ── Fuzzy reranking ───────────────────────────────────────────────────────────

def test_fuzzy_rerank_adds_similarity_score_column():
    df = _make_df(["Alpha", "Beta", "Gamma"])
    result = fuzzy_rerank(df, "Alpha", threshold=0.0)
    assert "similarity_score" in result.columns


def test_fuzzy_rerank_results_sorted_descending():
    df = _make_df(["Alpha", "Aleph", "Zebra", "Zeta"])
    result = fuzzy_rerank(df, "Alpha", threshold=0.0)
    scores = result["similarity_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_fuzzy_rerank_respects_max_rows():
    df = _make_df(["Aaaa", "Aaab", "Aaac", "Aaad", "Aaae"])
    result = fuzzy_rerank(df, "Aaaa", threshold=0.0, max_rows=3)
    assert len(result) <= 3


def test_fuzzy_rerank_respects_threshold():
    # Names that are completely unrelated to the target should be filtered out
    df = _make_df(["Aaaa", "Zzzz", "Qqqq"])
    result = fuzzy_rerank(df, "Aaaa", threshold=0.95)
    # Only the exact match should survive at 0.95 threshold
    assert all(s >= 0.95 for s in result["similarity_score"].tolist())


def test_fuzzy_rerank_exact_single_word_match_scores_one():
    # An exact match must always return similarity_score == 1.0
    df = _make_df(["Exact", "Something Else"])
    result = fuzzy_rerank(df, "Exact", threshold=0.0)
    exact_row = result[result["member_name"] == "Exact"]
    assert not exact_row.empty
    assert exact_row.iloc[0]["similarity_score"] == 1.0


def test_fuzzy_rerank_exact_multi_word_match_scores_one():
    # Regression: two-word exact target must score 1.0 and rank first.
    # Previously, individual words were compared against the full target string
    # and failed the length-difference guard, causing a score of 0.
    target = "Foo Bar"
    exact_name = "Foo Bar"
    similar_name = "Foobar Xyz"
    unrelated_name = "Zzz Qqq"
    df = _make_df([exact_name, similar_name, unrelated_name])

    result = fuzzy_rerank(df, target, threshold=0.80)
    names = result["member_name"].tolist()

    assert exact_name in names, "Exact multi-word name must be returned"
    assert names[0] == exact_name, "Exact match must rank first"
    assert result.iloc[0]["similarity_score"] == 1.0


def test_fuzzy_rerank_prefix_names_match_shorter_target():
    # A short target should match names that start with that prefix
    # e.g. target "Ram" should match "Ramu", "Rama" (prefix variants)
    prefix = "Ram"
    prefix_variants = ["Ramu", "Rama"]
    unrelated = "Zzz"
    df = _make_df(prefix_variants + [unrelated])

    result = fuzzy_rerank(df, prefix, threshold=0.75)
    names = result["member_name"].tolist()

    for name in prefix_variants:
        assert name in names, f"{name!r} should match prefix target {prefix!r}"
    assert unrelated not in names


def test_fuzzy_rerank_returns_empty_for_empty_dataframe():
    empty_df = pd.DataFrame(columns=["member_name"])
    assert fuzzy_rerank(empty_df, "Anything").empty is True


def test_fuzzy_rerank_graceful_when_no_name_column():
    # DataFrame with no name column — should return unchanged (no crash, no score col)
    no_name_df = pd.DataFrame({"age": [30, 25]})
    result = fuzzy_rerank(no_name_df, "Anything")
    assert "similarity_score" not in result.columns
