from validation.sql_validator import SQLValidator


def test_validator_accepts_known_join():
    sql = "SELECT member.member_name FROM member JOIN family ON member.family_id = family.family_id WHERE family.district = 'Jaipur';"
    result = SQLValidator().validate(sql)
    assert result.valid, result.errors


def test_validator_accepts_known_join_with_aliases():
    sql = "SELECT m.member_name FROM member AS m JOIN bank_details AS b ON m.member_id = b.member_id WHERE m.gender = 'Female';"
    result = SQLValidator().validate(sql)
    assert result.valid, result.errors


def test_validator_rejects_hallucinated_column():
    sql = "SELECT member.fake_column FROM member;"
    result = SQLValidator().validate(sql)
    assert not result.valid
    assert "Unknown columns" in "; ".join(result.errors)


def test_validator_rejects_write_statement():
    result = SQLValidator().validate("DROP TABLE member;")
    assert not result.valid


def test_validator_rejects_select_plus_write_statement():
    result = SQLValidator().validate("SELECT member.member_name FROM member; DELETE FROM member;")
    assert not result.valid
    assert "Only one SQL statement is allowed." in result.errors


def test_validator_rejects_select_into():
    result = SQLValidator().validate("SELECT member.member_name INTO backup_member FROM member;")
    assert not result.valid


def test_validator_rejects_qualified_column_from_unjoined_table():
    result = SQLValidator().validate("SELECT member.member_name FROM member WHERE family.district = 'Jaipur';")
    assert not result.valid
    assert "Qualified column references tables not present in FROM/JOIN" in "; ".join(result.errors)


def test_post_process_sql_rewrites_name_equals():
    from app import _post_process_sql
    sql = "SELECT member.member_name FROM member WHERE member.member_name = 'Vijay';"
    processed = _post_process_sql(sql)
    assert "member.member_name LIKE '%Vijay%'" in processed

    # Multi-word name should also be rewritten to LIKE with wildcards
    sql_multi = "SELECT member.member_name FROM member WHERE member.member_name = 'Vijay Kumar Laxmi';"
    processed_multi = _post_process_sql(sql_multi)
    assert "member.member_name LIKE '%Vijay Kumar Laxmi%'" in processed_multi

    # Categorical fields (gender, marital_status, caste_category) should be canonicalized in casing
    sql_cat = "SELECT * FROM member WHERE gender = 'male' AND caste_category = 'obc';"
    processed_cat = _post_process_sql(sql_cat)
    assert "gender = 'Male'" in processed_cat
    assert "caste_category = 'OBC'" in processed_cat

    # District fields should be canonicalized to exact case-insensitive matches from metadata list
    sql_dist = "SELECT * FROM family WHERE district = 'sawai madhopur';"
    processed_dist = _post_process_sql(sql_dist)
    assert "district = 'Sawai Madhopur'" in processed_dist


