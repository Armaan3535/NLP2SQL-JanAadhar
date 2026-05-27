from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnMeta:
    table: str
    column: str
    description: str
    data_type: str
    aliases: list[str] = field(default_factory=list)
    indexed: bool = False
    sample_values: list[str] = field(default_factory=list)
    semantic_name: str | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.table}.{self.column}"

    @property
    def business_name(self) -> str:
        return self.semantic_name or self.column


@dataclass(frozen=True)
class TableMeta:
    table: str
    description: str
    aliases: list[str]


RAJASTHAN_DISTRICTS_41 = [
    "Ajmer",
    "Alwar",
    "Balotra",
    "Banswara",
    "Baran",
    "Barmer",
    "Beawar",
    "Bharatpur",
    "Bhilwara",
    "Bikaner",
    "Bundi",
    "Chittorgarh",
    "Churu",
    "Dausa",
    "Deeg",
    "Didwana-Kuchaman",
    "Dholpur",
    "Dungarpur",
    "Hanumangarh",
    "Jaipur",
    "Jaisalmer",
    "Jalore",
    "Jhalawar",
    "Jhunjhunu",
    "Jodhpur",
    "Karauli",
    "Khairthal-Tijara",
    "Kota",
    "Kotputli-Behror",
    "Nagaur",
    "Pali",
    "Phalodi",
    "Pratapgarh",
    "Rajsamand",
    "Salumbar",
    "Sawai Madhopur",
    "Sikar",
    "Sirohi",
    "Sri Ganganagar",
    "Tonk",
    "Udaipur",
]

DISTRICT_ALIASES = [
    "district",
    "zilla",
    "city",
    "location",
    "region",
    *[district.lower() for district in RAJASTHAN_DISTRICTS_41],
    "kotputli",
    "ganganagar",
]


TABLES: list[TableMeta] = [
    TableMeta("family", "Household and Jan Aadhaar family geographical details", ["family", "household", "jan aadhaar", "address", "location"]),
    TableMeta("member", "Citizen member demographics, identity, and social profile", ["citizen", "member", "person", "resident", "people", "beneficiary"]),
    TableMeta("bank_details", "Bank account details and payment information", ["bank", "account", "ifsc", "payment", "dbt"]),
]


COLUMNS: list[ColumnMeta] = [
    # ── family ───────────────────────────────────────────────────────────────
    ColumnMeta("family", "family_id", "Primary family identifier used to join members", "integer", ["family id", "household id"], True),
    ColumnMeta("family", "jan_aadhaar_number", "Jan Aadhaar family enrollment number", "string", ["jan aadhaar number", "janaadhaar", "family card", "enrollment id"], True),
    ColumnMeta("family", "family_head_name", "Name of the family head (HOF)", "string", ["head", "head of family", "name of head"], True),
    ColumnMeta("family", "district", "District or zilla where the family resides", "string", DISTRICT_ALIASES, True, RAJASTHAN_DISTRICTS_41),
    ColumnMeta("family", "city", "Urban city name — NULL for all rural families (80% of records). Only populated when is_rural=0.", "string", ["city", "town", "urban area"], True),
    ColumnMeta("family", "block", "Administrative block or tehsil — NULL for urban families. Use for sub-district location queries.", "string", ["block", "tehsil", "subdistrict", "taluka"], True),
    ColumnMeta("family", "gram_panchayat", "Gram panchayat name — NULL for urban families", "string", ["gram panchayat", "panchayat", "gp"], True),
    ColumnMeta("family", "village", "Village name — NULL for urban families. Use for village-level location queries.", "string", ["village", "gaon", "gram"], True),
    ColumnMeta("family", "ward", "Municipal or urban ward name — NULL for rural families", "string", ["ward"], True),
    ColumnMeta(
        "family", "is_rural",
        "Whether family location is rural (1) or urban (0). INTEGER: 1=rural, 0=urban.",
        "integer",
        ["rural", "urban", "is rural", "countryside", "city dwellers", "village people"],
        True,
        ["1", "0"],
    ),

    # ── member ───────────────────────────────────────────────────────────────
    ColumnMeta("member", "member_id", "Primary citizen member identifier", "integer", ["member id", "citizen id"], True),
    ColumnMeta("member", "family_id", "Foreign key linking member to family", "integer", ["family id"], True),
    ColumnMeta("member", "jan_aadhaar_member_id", "Unique Jan Aadhaar member ID", "string", ["jan aadhaar member id"], True),
    ColumnMeta("member", "member_name", "Citizen full name", "string", ["name", "person name", "beneficiary name", "citizen name"], True),
    ColumnMeta("member", "father_name", "Father name", "string", ["father", "father's name", "pita"]),
    ColumnMeta("member", "mother_name", "Mother name", "string", ["mother", "mother's name", "mata"]),
    ColumnMeta("member", "spouse_name", "Spouse name — NULL for unmarried members", "string", ["spouse", "husband name", "wife name", "pati", "patni"]),
    ColumnMeta("member", "date_of_birth", "Date of birth", "date", ["dob", "birth date", "date of birth"]),
    ColumnMeta(
        "member", "age",
        "Citizen age in years (integer). Range in dataset: 8–103.",
        "integer",
        ["age", "old age", "adult", "minor", "senior", "elderly", "child", "children",
         "above", "below", "older than", "younger than", "between"],
        True,
    ),
    ColumnMeta(
        "member", "gender",
        "Citizen gender. Exact stored values: 'Male' or 'Female'.",
        "string",
        ["gender", "sex", "male", "female", "man", "woman", "boy", "girl",
         "boys", "girls", "men", "women", "ladies", "gents"],
        True,
        ["Male", "Female"],
    ),
    ColumnMeta("member", "mobile_number", "Citizen mobile phone number", "string", ["mobile", "phone", "contact number"]),
    ColumnMeta(
        "member", "caste_category",
        "Citizen caste category. Exact stored values: 'SC', 'ST', 'OBC', 'GEN'. NOTE: 'General' in speech maps to 'GEN' in the DB.",
        "string",
        ["caste category", "category", "sc", "st", "obc", "general", "gen"],
        True,
        ["SC", "ST", "OBC", "GEN"],
    ),
    ColumnMeta(
        "member", "caste",
        "Detailed caste name (numbers removed during import). Values are mixed case with many spelling variants; always use LIKE for caste searches.",
        "string",
        ["caste", "caste detail", "community", "jat", "mina", "rajput", "brahman", "bairwa",
         "jain", "gurjar", "gujar", "bazigar", "dhobi", "darzi", "valmiki", "fakir", "daroga",
         "chhipa", "दलित", "जाट", "राजपूत", "मीना", "महाजन", "बाजीगर"],
        True,
        ["Jat", "Arai", "Fakir", "Mina", "Rajput", "Gujar", "Jain", "Brahman", "Bairwa",
         "Bazigar", "Dangi", "Dhobi", "Darzi", "Daroga", "Valmiki", "Chhipa (Chhipi)",
         "Deshwali", "Dasnam Gauswami", "Home Maker", "Sindhi"],
    ),
    ColumnMeta(
        "member", "relation_with_hof",
        (
            "Relationship of member with the Head of Family (HOF). "
            "IMPORTANT: Most HOFs are female (Self+Female=556) but 12 HOFs are Male (Self+Male=12). "
            "The HOF's own row has relation_with_hof='Self'. "
            "The HOF's husband has relation_with_hof='Husband'. "
            "Children are 'Son' or 'Daughter'. "
            "All exact stored values: Self, Son, Daughter, Husband, Daughter-in-law, Grand Daughter, Grand Son."
        ),
        "string",
        ["relation", "relationship", "son", "daughter", "wife", "husband", "self",
         "daughter-in-law", "grand daughter", "grand son", "grandchild"],
        True,
        ["Self", "Son", "Daughter", "Husband", "Daughter-in-law", "Grand Daughter", "Grand Son"],
    ),
    ColumnMeta(
        "member", "member_type",
        "HOF = Head of Family record; MEM = regular family member. Exact stored values: 'HOF', 'MEM'.",
        "string",
        ["member type", "hof", "head of family", "mem", "family head"],
        True,
        ["HOF", "MEM"],
    ),
    ColumnMeta(
        "member", "marital_status",
        "Marital status. Exact stored values: 'Married', 'Unmarried', 'Widow'. No 'Divorced' or 'Separated' values exist.",
        "string",
        ["marital", "married", "unmarried", "widow", "widowed", "single", "divorced", "separated"],
        True,
        ["Married", "Unmarried", "Widow"],
    ),
    ColumnMeta(
        "member", "income",
        "Annual citizen income in rupees (integer). Range: 1–2,000,000. About 268 records have NULL/0 income.",
        "integer",
        ["income", "earning", "salary", "annual income", "rupees", "wages"],
        True,
    ),
    ColumnMeta(
        "member", "occupation",
        "Citizen occupation. Exact stored values shown below. Use LIKE for partial matches.",
        "string",
        ["occupation", "job", "work", "profession", "employed", "farmer", "labourer", "student",
         "homemaker", "home maker", "unemployed", "business", "government"],
        True,
        ["Home Maker", "Farmer", "Others", "Labourer", "Unemployed", "State personnel",
         "Self-Employed", "Autonomous organization employee", "Businessman",
         "Contractual Employee", "PSU/bank Emp.", "Student"],
    ),
    ColumnMeta(
        "member", "minority",
        "Minority community. Exact stored values: 'Muslim', 'Jain', or NULL. 96% of records are NULL (not minority). Always check IS NOT NULL when querying.",
        "string",
        ["minority", "religious minority", "muslim", "muslims", "jain", "jains"],
        True,
        ["Muslim", "Jain"],
    ),
    ColumnMeta(
        "member", "education",
        (
            "Citizen education qualification. Exact stored values (case-sensitive): "
            "'illiterate' (lowercase!), 'Literate', '5 Pass', '8 Pass', '10 Pass', '12 Pass', 'Graduate', 'Post Graduate', 'Other'. "
            "NOTE: 'illiterate' is stored all-lowercase; always filter with LIKE or LOWER()."
        ),
        "string",
        ["education", "qualification", "illiterate", "literate", "graduate", "pass",
         "school", "10th", "12th", "matric", "intermediate", "post graduate", "pg"],
        True,
        ["illiterate", "Literate", "5 Pass", "8 Pass", "10 Pass", "12 Pass", "Graduate", "Post Graduate", "Other"],
    ),

    # ── bank_details ─────────────────────────────────────────────────────────
    ColumnMeta("bank_details", "bank_id", "Primary bank detail identifier", "integer", ["bank id"], True),
    ColumnMeta("bank_details", "member_id", "Foreign key linking bank details to member", "integer", ["member id"], True),
    ColumnMeta("bank_details", "bank_account", "Bank account number", "string", ["account", "bank account", "account number"], True),
    ColumnMeta(
        "bank_details", "bank_name",
        "Bank name (stored in UPPER CASE for most banks; some use Title Case). Always use LIKE for bank name searches.",
        "string",
        ["bank", "bank name", "sbi", "pnb", "bob", "hdfc", "icici", "cooperative bank", "gramin bank"],
        True,
        ["STATE BANK OF INDIA", "BANK OF BARODA", "PUNJAB NATIONAL BANK",
         "CENTRAL BANK OF INDIA", "UCO BANK", "UNION BANK OF INDIA",
         "CANARA BANK", "Rajasthan Gramin Bank", "ICICI BANK LIMITED",
         "HDFC BANK", "BANK OF INDIA"],
    ),
    ColumnMeta("bank_details", "ifsc_code", "IFSC code", "string", ["ifsc", "ifsc code"], True),
]


RELATIONSHIPS = [
    {"from_table": "member", "from_column": "family_id", "to_table": "family", "to_column": "family_id"},
    {"from_table": "bank_details", "from_column": "member_id", "to_table": "member", "to_column": "member_id"},
]


def all_table_names() -> set[str]:
    return {table.table for table in TABLES}


def columns_by_table() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for column in COLUMNS:
        result.setdefault(column.table, set()).add(column.column)
    return result
