from pathlib import Path

import pandas as pd
import pytest

from database.excel_importer import import_excel_dataset
from database.query_results import execute_select_preview


def test_import_excel_and_show_query_entries(tmp_path: Path):
    excel_path = tmp_path / "dummy.xlsx"
    database_url = f"sqlite:///{(tmp_path / 'test.sqlite').as_posix()}"
    pd.DataFrame(
        [
            {
                "DISTRICT_NAME_ENG": "Jaipur",
                "IS_RURAL": 1,
                "BLOCK_NAME_ENG": "Sanganer",
                "CITY_NAME_ENG": None,
                "WARD_NAME_ENG": None,
                "GP_NAME_ENG": "Gram",
                "VILL_NAME_ENG": "Village",
                "ENROLLMENT_ID": "JAN-001",
                "MEMBER_ID": 101,
                "NAME_EN": "Ravi Kumar",
                "FATHER_NAME_EN": "Father",
                "MOTHER_NAME_EN": "Mother",
                "SPOUCE_NAME_EN": None,
                "DOB": "01-Jan-2000",
                "AGE": 25,
                "GENDER": "Male",
                "CASTE_CATEGORY": "OBC",
                "MARITAL_STATUS": "Unmarried",
                "BANK": "State Bank",
                "IFSC_CODE": "SBIN001",
                "ACCOUNT_NO": "XXXXX123",
                "MOBILE_NO": "XXXX123",
                "IS_RURAL": 1,
                "MEM_TYPE": "MEM",
                "RELATION_WITH_HOF": "Son",
                "CASTE": "Detailed Community",
                "INCOME": 1000,
                "OCCUPATION": "Others",
                "MINORITY": "No",
                "EDUCATION": "Graduate",
            }
        ]
    ).to_excel(excel_path, index=False)

    report = import_excel_dataset(excel_path, database_url=database_url)
    preview = execute_select_preview(
        "SELECT member.member_name, member.age, member.education FROM member JOIN family ON member.family_id = family.family_id "
        "WHERE member.gender = 'Male' AND family.district = 'Jaipur';",
        database_url=database_url,
    )
    assert report.members_loaded == 1
    assert preview.rows.to_dict(orient="records") == [{"member_name": "Ravi Kumar", "age": 25, "education": "Graduate"}]


def test_result_preview_refuses_write_sql(tmp_path: Path):
    database_url = f"sqlite:///{(tmp_path / 'test.sqlite').as_posix()}"
    with pytest.raises(ValueError, match="unsafe SQL"):
        execute_select_preview("DELETE FROM member;", database_url=database_url)
