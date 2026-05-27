from database.schema_metadata import COLUMNS, ColumnMeta, RAJASTHAN_DISTRICTS_41, RELATIONSHIPS


def test_pension_and_geography_metadata_exist():
    names = {column.qualified_name for column in COLUMNS}
    assert "bank_details.bank_name" in names
    assert "family.district" in names
    assert "member.gender" in names


def test_relationships_include_member_family():
    assert any(
        relationship["from_table"] == "member" and relationship["to_table"] == "family"
        for relationship in RELATIONSHIPS
    )


def test_rajasthan_districts_match_current_wikipedia_count():
    assert len(RAJASTHAN_DISTRICTS_41) == 41
    assert "Bikaner" in RAJASTHAN_DISTRICTS_41
    assert "Kotputli-Behror" in RAJASTHAN_DISTRICTS_41
    assert "Anupgarh" not in RAJASTHAN_DISTRICTS_41
    assert "Jaipur Rural" not in RAJASTHAN_DISTRICTS_41
    assert "Sanchore" not in RAJASTHAN_DISTRICTS_41


def test_column_metadata_supports_legacy_misspelled_physical_names():
    column = ColumnMeta(
        table="member",
        column="gendr",
        description="Citizen gender",
        data_type="string",
        aliases=["gender", "male", "female"],
        semantic_name="gender",
    )
    assert column.qualified_name == "member.gendr"
    assert column.business_name == "gender"
