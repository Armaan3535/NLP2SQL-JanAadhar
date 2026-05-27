from __future__ import annotations

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Family(Base):
    __tablename__ = "family"

    family_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jan_aadhaar_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    family_head_name: Mapped[str] = mapped_column(String(120), index=True)
    district: Mapped[str] = mapped_column(String(80), index=True)
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    block: Mapped[str | None] = mapped_column(String(80), index=True)
    gram_panchayat: Mapped[str | None] = mapped_column(String(100), index=True)
    village: Mapped[str | None] = mapped_column(String(100), index=True)
    ward: Mapped[str | None] = mapped_column(String(40), index=True)
    is_rural: Mapped[bool | None] = mapped_column(Boolean, index=True)

    members: Mapped[list["Member"]] = relationship(back_populates="family")


class Member(Base):
    __tablename__ = "member"

    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("family.family_id"), index=True)
    jan_aadhaar_member_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    member_name: Mapped[str] = mapped_column(String(120), index=True)
    father_name: Mapped[str | None] = mapped_column(String(120))
    mother_name: Mapped[str | None] = mapped_column(String(120))
    spouse_name: Mapped[str | None] = mapped_column(String(120))
    date_of_birth: Mapped[Date | None] = mapped_column(Date)
    age: Mapped[int | None] = mapped_column(Integer, index=True)
    gender: Mapped[str] = mapped_column(String(16), index=True)
    mobile_number: Mapped[str | None] = mapped_column(String(16))
    caste_category: Mapped[str | None] = mapped_column(String(32), index=True)
    marital_status: Mapped[str | None] = mapped_column(String(32), index=True)
    member_type: Mapped[str | None] = mapped_column(String(20), index=True)
    relation_with_hof: Mapped[str | None] = mapped_column(String(40), index=True)
    caste: Mapped[str | None] = mapped_column(String(180), index=True)
    income: Mapped[int | None] = mapped_column(Integer, index=True)
    occupation: Mapped[str | None] = mapped_column(String(80), index=True)
    minority: Mapped[str | None] = mapped_column(String(40), index=True)
    education: Mapped[str | None] = mapped_column(String(80), index=True)

    family: Mapped[Family] = relationship(back_populates="members")
    bank_details: Mapped[list["BankDetails"]] = relationship(back_populates="member")


class BankDetails(Base):
    __tablename__ = "bank_details"

    bank_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.member_id"), index=True)
    bank_account: Mapped[str] = mapped_column(String(32), index=True)
    bank_name: Mapped[str] = mapped_column(String(120), index=True)
    ifsc_code: Mapped[str] = mapped_column(String(16), index=True)

    member: Mapped[Member] = relationship(back_populates="bank_details")


Index("ix_member_gender_caste_age", Member.gender, Member.caste_category, Member.age)
Index("ix_family_geo", Family.district, Family.block, Family.gram_panchayat, Family.village)

