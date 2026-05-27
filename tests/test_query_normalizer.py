from normalization.query_normalizer import normalize_query


def test_normalizer_corrects_common_user_typos():
    result = normalize_query("all femail benificiaries in jaipor")
    assert result.normalized == "all female beneficiaries in Jaipur"
    assert result.corrections["femail"] == "female"
    assert result.corrections["benificiaries"] == "beneficiaries"
    assert result.corrections["jaipor"] == "Jaipur"


def test_normalizer_corrects_district_typo():
    result = normalize_query("boys above 21 in jodpur")
    assert "Jodhpur" in result.normalized


def test_normalizer_preserves_valid_natural_language():
    question = "Show all female beneficiaries receiving pension in Jaipur district."
    result = normalize_query(question)
    assert result.normalized == question
    assert result.corrections == {}
