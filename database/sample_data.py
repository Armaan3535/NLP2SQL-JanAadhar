from __future__ import annotations

from datetime import date

from sqlalchemy import select

from database.connection import create_tables, get_session
from database.models import BankDetails, Family, Member


def seed_demo_data() -> None:
    create_tables()
    with get_session() as session:
        if session.scalar(select(Family).limit(1)):
            return
        families = [
            Family(family_id=1, jan_aadhaar_number="JAN100000001", family_head_name="Sita Sharma", district="Jaipur", city="Jaipur", block="Sanganer", gram_panchayat=None, village=None, ward="12", is_rural=False),
            Family(family_id=2, jan_aadhaar_number="JAN100000002", family_head_name="Ramesh Meghwal", district="Jaipur", city=None, block="Kotputli", gram_panchayat="Kotputli GP", village="Kalyanpura", ward=None, is_rural=True),
            Family(family_id=3, jan_aadhaar_number="JAN100000003", family_head_name="Asha Devi", district="Ajmer", city=None, block="Kishangarh", gram_panchayat="Roopangarh", village="Roopangarh", ward=None, is_rural=True),
        ]
        members = [
            Member(
                member_id=1, family_id=1, jan_aadhaar_member_id="JAN100000001-1", member_name="Sita Sharma", 
                father_name="Hari Prasad", mother_name="Pramod Devi", spouse_name="Late Mohan Sharma", 
                date_of_birth=date(1958, 5, 10), age=68, gender="Female", mobile_number="XXXXX11111", 
                caste_category="GEN", marital_status="Widow", member_type="HOF", relation_with_hof="Self", 
                caste="Brahman", income=12000, occupation="Retired", minority=None, education="Graduate"
            ),
            Member(
                member_id=2, family_id=2, jan_aadhaar_member_id="JAN100000002-2", member_name="Ramesh Meghwal", 
                father_name="Kalu Ram", mother_name="Kamla Devi", spouse_name="Kavita Meghwal", 
                date_of_birth=date(1982, 8, 15), age=44, gender="Male", mobile_number="XXXXX22222", 
                caste_category="SC", marital_status="Married", member_type="HOF", relation_with_hof="Self", 
                caste="Balmiki", income=45000, occupation="Others", minority=None, education="10 Pass"
            ),
            Member(
                member_id=3, family_id=2, jan_aadhaar_member_id="JAN100000002-3", member_name="Kavita Meghwal", 
                father_name="Ram Lal", mother_name="Sarla Devi", spouse_name="Ramesh Meghwal", 
                date_of_birth=date(1987, 3, 20), age=39, gender="Female", mobile_number="XXXXX33333", 
                caste_category="SC", marital_status="Married", member_type="MEM", relation_with_hof="Wife", 
                caste="Balmiki", income=0, occupation="Housewife", minority=None, education="Literate"
            ),
            Member(
                member_id=4, family_id=3, jan_aadhaar_member_id="JAN100000003-4", member_name="Asha Devi", 
                father_name="Deva Ram", mother_name="Bhurli Devi", spouse_name="Late Ghanshyam", 
                date_of_birth=date(1954, 11, 25), age=72, gender="Female", mobile_number="XXXXX44444", 
                caste_category="OBC", marital_status="Widow", member_type="HOF", relation_with_hof="Self", 
                caste="Jat", income=8000, occupation="Pensioner", minority=None, education="illiterate"
            ),
        ]
        banks = [
            BankDetails(bank_id=1, member_id=1, bank_account="11110001", bank_name="STATE BANK OF INDIA", ifsc_code="SBIN0001"),
            BankDetails(bank_id=2, member_id=2, bank_account="11110002", bank_name="State Bank of India", ifsc_code="SBIN0002"),
        ]
        session.add_all(families + members + banks)
        session.commit()


if __name__ == "__main__":
    seed_demo_data()
    print("Demo database seeded.")
