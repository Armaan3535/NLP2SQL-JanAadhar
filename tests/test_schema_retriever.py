from retrieval.schema_retriever import SchemaRetriever


class EmptyStore:
    def search(self, question, top_k):
        return []


class NoisyStore:
    def search(self, question, top_k):
        noisy_columns = [
            "family.block",
            "family.district",
            "family.gram_panchayat",
            "family.jan_aadhaar_number",
            "member.mobile_number",
            "member.age",
            "member.caste_category",
            "member.date_of_birth",
            "member.gender",
            "member.jan_aadhaar_member_id",
        ]
        return [
            {
                "kind": "column",
                "table": qualified_name.split(".")[0],
                "qualified_name": qualified_name,
                "score": 0.9,
            }
            for qualified_name in noisy_columns
        ]


def test_retriever_adds_explicit_geography_columns():
    result = SchemaRetriever(EmptyStore()).retrieve("all female citizens in Jaipur district")
    assert "family" in result.tables
    assert "family.district" in result.columns
    assert "member.gender" in result.columns
    assert "member.member_name" in result.columns


def test_retriever_adds_boys_age_and_jodhpur_columns():
    result = SchemaRetriever(EmptyStore()).retrieve("show me all boys above 18 in jodhpur")
    assert "family.district" in result.columns
    assert "member.gender" in result.columns
    assert "member.age" in result.columns
    assert "member.caste_category" not in result.columns
    assert len(result.columns) <= 6


def test_retriever_handles_bikaner_as_district():
    result = SchemaRetriever(EmptyStore()).retrieve("all boys above 21 in bikaner")
    assert "family.district" in result.columns
    assert "member.gender" in result.columns
    assert "member.age" in result.columns
    assert "member.member_name" in result.columns


def test_retriever_uses_generic_location_fallback():
    result = SchemaRetriever(EmptyStore()).retrieve("all girls above 21 in phulera")
    assert "family.district" in result.columns
    assert "member.gender" in result.columns
    assert "member.age" in result.columns


def test_retriever_prunes_noisy_unrequested_domains():
    result = SchemaRetriever(NoisyStore()).retrieve("All boys above 21 in jaipur")
    assert "family" in result.tables
    assert "member" in result.tables
    expected = {
        "family.district",
        "family.family_id",
        "member.age",
        "member.family_id",
        "member.gender",
        "member.member_name",
    }
    assert expected.issubset(set(result.columns))


def test_retriever_uses_education_and_minority_for_illiterate_muslims():
    result = SchemaRetriever(NoisyStore()).retrieve("Show all illiterate muslims in Jaipur")
    assert "member.education" in result.columns
    assert "member.minority" in result.columns
    assert "family.district" in result.columns
    assert "member.caste_category" not in result.columns
    assert "member.gender" not in result.columns
