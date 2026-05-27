CREATE TABLE family (
    family_id INTEGER PRIMARY KEY,
    jan_aadhaar_number VARCHAR(20) UNIQUE NOT NULL,
    family_head_name VARCHAR(120) NOT NULL,
    permanent_address TEXT,
    current_address TEXT,
    district VARCHAR(80) NOT NULL,
    city VARCHAR(80),
    block VARCHAR(80),
    gram_panchayat VARCHAR(100),
    village VARCHAR(100),
    ward VARCHAR(40),
    ration_card_number VARCHAR(40),
    is_rural BOOLEAN
);

CREATE TABLE member (
    member_id INTEGER PRIMARY KEY,
    family_id INTEGER NOT NULL REFERENCES family(family_id),
    jan_aadhaar_member_id VARCHAR(24) UNIQUE NOT NULL,
    member_name VARCHAR(120) NOT NULL,
    father_name VARCHAR(120),
    mother_name VARCHAR(120),
    spouse_name VARCHAR(120),
    date_of_birth DATE,
    age INTEGER,
    gender VARCHAR(16) NOT NULL,
    mobile_number VARCHAR(16),
    email VARCHAR(120),
    photo_path VARCHAR(255),
    aadhaar_masked VARCHAR(20),
    voter_id VARCHAR(30),
    pan_number VARCHAR(20),
    caste_category VARCHAR(32),
    religion VARCHAR(40),
    marital_status VARCHAR(32),
    disability_status BOOLEAN DEFAULT 0,
    member_type VARCHAR(20),
    relation_with_hof VARCHAR(40),
    caste VARCHAR(180),
    income INTEGER,
    occupation VARCHAR(80),
    minority VARCHAR(40),
    education VARCHAR(80)
);

CREATE TABLE bank_details (
    bank_id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member(member_id),
    bank_account VARCHAR(32) NOT NULL,
    bank_name VARCHAR(120) NOT NULL,
    ifsc_code VARCHAR(16) NOT NULL,
    dbt_status VARCHAR(24) NOT NULL
);

CREATE TABLE scheme_benefits (
    scheme_benefit_id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member(member_id),
    scheme_name VARCHAR(120) NOT NULL,
    bpl_status VARCHAR(16),
    apl_status VARCHAR(16),
    nfsa_status VARCHAR(24),
    pension_eligibility VARCHAR(24),
    beneficiary_status VARCHAR(24),
    benefit_amount INTEGER
);

CREATE TABLE verification (
    verification_id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL UNIQUE REFERENCES member(member_id),
    ekyc_status VARCHAR(24) NOT NULL,
    aadhaar_seeding_status VARCHAR(24) NOT NULL,
    jan_aadhaar_status VARCHAR(24) NOT NULL,
    last_updated_date DATE
);

CREATE INDEX ix_family_geo ON family(district, block, gram_panchayat, village);
CREATE INDEX ix_member_gender_caste_age ON member(gender, caste_category, age);
CREATE INDEX ix_scheme_pension_beneficiary ON scheme_benefits(pension_eligibility, beneficiary_status);
CREATE INDEX ix_verification_ekyc_aadhaar ON verification(ekyc_status, aadhaar_seeding_status);
