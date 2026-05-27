from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from sqlalchemy import text
from database.connection import get_engine, get_session
from database.models import BankDetails, Family, Member


REQUIRED_COLUMNS = {
    "DISTRICT_NAME_ENG",
    "ENROLLMENT_ID",
    "MEMBER_ID",
    "NAME_EN",
    "AGE",
    "GENDER",
}

DISTRICT_VALUE_NORMALIZATION = {
    "Balotara": "Balotra",
}


@dataclass(frozen=True)
class DatasetImportReport:
    source_name: str
    members_loaded: int
    families_loaded: int
    bank_records_loaded: int
    skipped_bank_records: int


def clean_caste(val) -> str | None:
    if val is None or pd.isna(val):
        return None
    cleaned = str(val).strip()
    # Strip leading numbers followed by optional spaces
    cleaned = re.sub(r"^\d+\s*", "", cleaned)
    # Title case to standardize mixed case entries in English
    return cleaned.title() if cleaned else None


def import_excel_dataset(
    source: str | Path | BinaryIO,
    source_name: str | None = None,
    database_url: str | None = None,
) -> DatasetImportReport:
    # 1. Read dataset
    if isinstance(source, (str, Path)) and str(source).lower().endswith(".csv"):
        data = pd.read_csv(source)
    else:
        data = pd.read_excel(source)

    # Clean up entirely empty or metadata rows
    data = data.dropna(how="all")
    if data.empty:
        raise ValueError("The provided dataset is empty.")

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(sorted(missing))}.")

    # Clean row values to dictionary
    rows = data.where(pd.notna(data), None).to_dict(orient="records")
    
    # 2. Group by ENROLLMENT_ID to map Families correctly
    family_map: dict[str, dict] = {}
    family_members_list: dict[str, list[dict]] = {}

    for row in rows:
        enrollment_id = _text(row.get("ENROLLMENT_ID"))
        member_id = _integer(row.get("MEMBER_ID"))
        if not enrollment_id or member_id is None:
            continue  # Skip rows missing crucial identifiers
        
        family_members_list.setdefault(enrollment_id, []).append(row)

    # 3. Build Families and Members
    families: list[Family] = []
    members: list[Member] = []
    banks: list[BankDetails] = []

    family_id_counter = 1
    for enrollment_id, m_rows in family_members_list.items():
        # Identify the Head of Family (HOF) or fallback to first member
        hof_row = m_rows[0]
        for r in m_rows:
            mem_type = _text(r.get("MEM_TYPE"))
            relation = _text(r.get("RELATION_WITH_HOF"))
            if (mem_type and mem_type.upper() == "HOF") or (relation and relation.lower() in ("self", "head")):
                hof_row = r
                break
        
        district = DISTRICT_VALUE_NORMALIZATION.get(str(hof_row["DISTRICT_NAME_ENG"]), str(hof_row["DISTRICT_NAME_ENG"]))
        
        families.append(
            Family(
                family_id=family_id_counter,
                jan_aadhaar_number=enrollment_id,
                family_head_name=str(hof_row["NAME_EN"]),
                district=district,
                city=_text(hof_row.get("CITY_NAME_ENG")),
                block=_text(hof_row.get("BLOCK_NAME_ENG")),
                gram_panchayat=_text(hof_row.get("GP_NAME_ENG")),
                village=_text(hof_row.get("VILL_NAME_ENG")),
                ward=_text(hof_row.get("WARD_NAME_ENG")),
                is_rural=_boolean(hof_row.get("IS_RURAL")),
            )
        )

        for r in m_rows:
            m_id = int(r["MEMBER_ID"])
            members.append(
                Member(
                    member_id=m_id,
                    family_id=family_id_counter,
                    jan_aadhaar_member_id=f"{enrollment_id}-{m_id}",
                    member_name=str(r["NAME_EN"]),
                    father_name=_text(r.get("FATHER_NAME_EN")),
                    mother_name=_text(r.get("MOTHER_NAME_EN")),
                    spouse_name=_text(r.get("SPOUCE_NAME_EN")),
                    date_of_birth=_date(r.get("DOB")),
                    age=_integer(r.get("AGE")),
                    gender=str(r["GENDER"]).title(),
                    mobile_number=_text(r.get("MOBILE_NO")),
                    caste_category=_text(r.get("CASTE_CATEGORY")),
                    marital_status=_text(r.get("MARITAL_STATUS")),
                    member_type=_text(r.get("MEM_TYPE")),
                    relation_with_hof=_text(r.get("RELATION_WITH_HOF")),
                    caste=clean_caste(r.get("CASTE")),
                    income=_integer(r.get("INCOME")),
                    occupation=_text(r.get("OCCUPATION")),
                    minority=_text(r.get("MINORITY")),
                    education=_text(r.get("EDUCATION")),
                )
            )

            if r.get("ACCOUNT_NO") and r.get("BANK") and r.get("IFSC_CODE"):
                banks.append(
                    BankDetails(
                        member_id=m_id,
                        bank_account=str(r["ACCOUNT_NO"]),
                        bank_name=str(r["BANK"]),
                        ifsc_code=str(r["IFSC_CODE"]),
                    )
                )
        
        family_id_counter += 1

    # 4. Truncate target tables non-destructively based on SQL dialect
    engine = get_engine(database_url)
    from database.models import Base
    Base.metadata.create_all(engine)
    dialect_name = engine.dialect.name
    
    with engine.begin() as conn:
        if dialect_name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = OFF;"))
            conn.execute(text("DELETE FROM bank_details;"))
            conn.execute(text("DELETE FROM member;"))
            conn.execute(text("DELETE FROM family;"))
            conn.execute(text("PRAGMA foreign_keys = ON;"))
        else:
            # PostgreSQL or standard ANSI SQL
            conn.execute(text("TRUNCATE TABLE bank_details, member, family RESTART IDENTITY CASCADE;"))

    # 5. Bulk ingest data high-performance
    with get_session(database_url) as session:
        session.add_all(families)
        session.add_all(members)
        session.add_all(banks)
        session.commit()

    resolved_name = source_name or getattr(source, "name", None) or str(source)
    return DatasetImportReport(
        source_name=Path(str(resolved_name)).name,
        members_loaded=len(members),
        families_loaded=len(families),
        bank_records_loaded=len(banks),
        skipped_bank_records=len(members) - len(banks),
    )


def _text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value).strip()


def _integer(value) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _date(value):
    if value is None or pd.isna(value):
        return None
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp.date()


def _boolean(value) -> bool | None:
    if value is None or pd.isna(value):
        return None
    try:
        return bool(int(float(value)))
    except (ValueError, TypeError):
        return None
