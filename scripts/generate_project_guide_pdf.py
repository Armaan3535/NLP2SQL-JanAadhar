from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "Jan_Aadhaar_NL2SQL_Project_Guide.pdf"


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=32,
        textColor=colors.HexColor("#17324d"),
        alignment=TA_CENTER,
        spaceAfter=16,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSubtitle",
        parent=styles["Normal"],
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#4c6475"),
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        name="H1Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=22,
        textColor=colors.HexColor("#17324d"),
        spaceBefore=10,
        spaceAfter=9,
    )
)
styles.add(
    ParagraphStyle(
        name="H2Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=17,
        textColor=colors.HexColor("#196b75"),
        spaceBefore=8,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#20303c"),
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="BulletCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.3,
        leading=13.5,
        leftIndent=14,
        firstLineIndent=-9,
        textColor=colors.HexColor("#20303c"),
        spaceAfter=3,
    )
)
styles.add(
    ParagraphStyle(
        name="SmallCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#536776"),
        spaceAfter=3,
    )
)
styles.add(
    ParagraphStyle(
        name="TableHead",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )
)
styles.add(
    ParagraphStyle(
        name="TableBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.1,
        leading=10.5,
        textColor=colors.HexColor("#20303c"),
    )
)
styles.add(
    ParagraphStyle(
        name="CodeCustom",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#142738"),
        leftIndent=6,
        rightIndent=6,
        spaceBefore=4,
        spaceAfter=7,
    )
)


def p(text: str, style: str = "BodyCustom") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str) -> Paragraph:
    return Paragraph(f"&#8226;&nbsp;&nbsp;{text}", styles["BulletCustom"])


def h1(text: str) -> Paragraph:
    return Paragraph(text, styles["H1Custom"])


def h2(text: str) -> Paragraph:
    return Paragraph(text, styles["H2Custom"])


def code(text: str) -> Preformatted:
    return Preformatted(text.strip("\n"), styles["CodeCustom"])


def data_table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    formatted = [[p(item, "TableHead") for item in headers]]
    formatted.extend([[p(item, "TableBody") for item in row] for row in rows])
    table = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#196b75")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f5f8f8")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f7f7")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c6d5d8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


class ArchitectureFlowchart(Flowable):
    def __init__(self, width: float):
        super().__init__()
        self.width = width
        self.height = 19.8 * cm

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        x = 0.55 * cm
        box_w = self.width - 1.1 * cm
        box_h = 1.32 * cm
        gap = 0.48 * cm
        steps = [
            ("1. User Question", "Natural language entered in Streamlit or CLI", "#17324d"),
            ("2. Query Normalization", "RapidFuzz fixes likely typos only; valid phrasing is preserved", "#196b75"),
            ("3. Query Embedding", "Ollama nomic-embed-text converts meaning into a numeric vector", "#196b75"),
            ("4. Schema Retrieval", "FAISS searches embedded table and column metadata", "#196b75"),
            ("5. Context Pruning", "Rules retain requested domains and required join keys only", "#196b75"),
            ("6. RAG Prompt Assembly", "Reduced schema context + allowed joins + question", "#94632a"),
            ("7. SQL Generation", "Ollama qwen2.5-coder:3b produces one SELECT statement", "#94632a"),
            ("8. SQL Validation", "Read-only, known columns/tables, valid joins, retrieved context", "#b44b35"),
            ("9. Result Display", "SQL, retrieved schema, confidence, EXPLAIN and timing", "#17324d"),
        ]
        y = self.height - box_h
        for index, (title, description, fill) in enumerate(steps):
            canvas.setFillColor(colors.HexColor(fill))
            canvas.roundRect(x, y, box_w, box_h, 7, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 9)
            canvas.drawString(x + 0.25 * cm, y + 0.78 * cm, title)
            canvas.setFont("Helvetica", 7.8)
            canvas.drawString(x + 0.25 * cm, y + 0.34 * cm, description)
            if index < len(steps) - 1:
                canvas.setStrokeColor(colors.HexColor("#91a9ad"))
                canvas.setLineWidth(1)
                arrow_x = self.width / 2
                canvas.line(arrow_x, y, arrow_x, y - gap + 0.12 * cm)
                canvas.line(arrow_x, y - gap + 0.12 * cm, arrow_x - 0.10 * cm, y - gap + 0.28 * cm)
                canvas.line(arrow_x, y - gap + 0.12 * cm, arrow_x + 0.10 * cm, y - gap + 0.28 * cm)
            y -= box_h + gap


class SchemaRelationshipDiagram(Flowable):
    def __init__(self, width: float):
        super().__init__()
        self.width = width
        self.height = 7.3 * cm

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        main_x = self.width / 2 - 2.2 * cm
        main_y = 2.6 * cm
        self._box(main_x, main_y, 4.4 * cm, 1.55 * cm, "member", "member_id, family_id, demographics", "#196b75")
        positions = [
            (0.2 * cm, 5.2 * cm, "family", "family_id, district, village"),
            (self.width - 5.0 * cm, 5.2 * cm, "bank_details", "member_id, dbt_status"),
            (0.2 * cm, 0.15 * cm, "scheme_benefits", "member_id, pension, NFSA"),
            (self.width - 5.0 * cm, 0.15 * cm, "verification", "member_id, eKYC"),
        ]
        centers = []
        for x, y, title, sub in positions:
            self._box(x, y, 4.8 * cm, 1.55 * cm, title, sub, "#17324d")
            centers.append((x + 2.4 * cm, y + 0.78 * cm))
        member_center = (main_x + 2.2 * cm, main_y + 0.78 * cm)
        canvas.setStrokeColor(colors.HexColor("#789196"))
        canvas.setLineWidth(0.8)
        for center in centers:
            canvas.line(member_center[0], member_center[1], center[0], center[1])

    def _box(self, x, y, width, height, title, subtitle, color):
        canvas = self.canv
        canvas.setFillColor(colors.HexColor(color))
        canvas.roundRect(x, y, width, height, 6, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8.8)
        canvas.drawCentredString(x + width / 2, y + 0.93 * cm, title)
        canvas.setFont("Helvetica", 6.8)
        canvas.drawCentredString(x + width / 2, y + 0.42 * cm, subtitle)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d5dfe1"))
    canvas.line(doc.leftMargin, 1.28 * cm, A4[0] - doc.rightMargin, 1.28 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#677b87"))
    canvas.drawString(doc.leftMargin, 0.88 * cm, "Jan Aadhaar NL2SQL | Local Retrieval-Augmented Text-to-SQL System")
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.88 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_story() -> list:
    body: list = []

    body.extend(
        [
            Spacer(1, 2.1 * cm),
            p("JAN AADHAAR NL2SQL", "CoverTitle"),
            p("A Local Retrieval-Augmented Natural Language to SQL Query Generation System", "CoverSubtitle"),
            Spacer(1, 0.6 * cm),
            p(
                "Technical project guide: vector embeddings, FAISS schema retrieval, RAG context construction, "
                "Ollama LLM generation, validation, optimization, and UI workflow.",
                "CoverSubtitle",
            ),
            Spacer(1, 1.4 * cm),
            data_table(
                ["Current Component", "Implementation"],
                [
                    ["SQL generation model", "Ollama qwen2.5-coder:3b (laptop-friendly default)"],
                    ["Embedding model", "Ollama nomic-embed-text"],
                    ["Vector search", "FAISS IndexFlatIP, persisted locally"],
                    ["Demo database", "SQLite through SQLAlchemy"],
                    ["Interface", "Streamlit UI and Python CLI"],
                    ["Security posture", "Single SELECT-only SQL validation gate"],
                ],
                [5.4 * cm, 10.2 * cm],
            ),
            Spacer(1, 1.2 * cm),
            p(f"Prepared from the implemented project code | {date.today().strftime('%d %B %Y')}", "CoverSubtitle"),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("1. Project Purpose"),
            p(
                "This project lets a user ask database questions in ordinary language and receive a SQL query. "
                "It is designed around a Jan Aadhaar-style relational database containing family, citizen member, "
                "welfare, banking, and verification information."
            ),
            p(
                "A question such as <b>Show all female beneficiaries receiving pension in Jaipur district</b> is "
                "translated into a query that joins only the necessary tables and uses only the required columns."
            ),
            h2("The Core Design Constraint"),
            p(
                "A real citizen registry can contain a very large schema and extremely large datasets. The full "
                "schema is therefore <b>not</b> sent to the language model for every request. Instead, the system "
                "searches a vector index of schema descriptions and sends a small, relevant schema context."
            ),
            h2("What the System Returns"),
            bullet("A generated, read-only SQL SELECT query."),
            bullet("The tables and columns retrieved for the question."),
            bullet("A schema retrieval confidence score."),
            bullet("An optional SQLite EXPLAIN plan and planning/execution time."),
            bullet("Visible spelling corrections when the input appears misspelled."),
            h1("2. End-to-End Architecture Flowchart"),
            p(
                "The following flowchart separates the three AI-related activities: embedding meaning, retrieving "
                "relevant knowledge, and generating SQL."
            ),
            ArchitectureFlowchart(16.5 * cm),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("3. What Vector Embeddings Are Doing"),
            h2("Simple Meaning"),
            p(
                "An embedding is a list of numbers representing the meaning of text. Texts with similar meaning "
                "produce vectors that are close to one another. For this project, embeddings do not represent "
                "citizen records; they represent <b>schema metadata</b> and the user's question."
            ),
            h2("Where Embeddings Are Used"),
            data_table(
                ["Moment", "Text Embedded", "Why"],
                [
                    [
                        "Index build",
                        "Table and column documents",
                        "Prepare a searchable map of the database schema.",
                    ],
                    [
                        "Each question",
                        "Normalized user question",
                        "Find columns semantically related to the user's intent.",
                    ],
                ],
                [3.0 * cm, 5.1 * cm, 7.5 * cm],
            ),
            h2("Schema Documents"),
            p(
                "Each table and each column becomes a short semantic document in "
                "<b>embeddings/faiss_store.py</b>. A column document carries its physical name, business meaning, "
                "description, type, aliases, and useful sample values."
            ),
            code(
                """
column member.gender
semantic name: gender
description: Citizen gender male female other;
             boy or boys means Male; girl or girls means Female
type: string
aliases: gender, sex, male, female, boy, boys, girl, girls
sample values: Male, Female, Other
"""
            ),
            p(
                "This also supports legacy schemas. If the physical database really has a misspelled column such "
                "as <b>member.gendr</b>, its metadata can set <b>semantic_name='gender'</b>. Retrieval understands "
                "the clean meaning, while generated SQL still uses the real physical column."
            ),
            h2("Embedding Model and Similarity"),
            bullet("Model: <b>nomic-embed-text</b>, executed locally through Ollama."),
            bullet("Vectors are normalized with NumPy after they are produced."),
            bullet("FAISS uses <b>IndexFlatIP</b>; inner product on normalized vectors acts like cosine similarity."),
            bullet("The persisted files are <b>data/schema.faiss</b> and <b>data/schema_metadata.json</b>."),
            h2("Why This Is Efficient"),
            p(
                "The index contains schema entries, not 8 crore citizen records. Its size grows with the number "
                "of tables and columns, so searching it remains lightweight even when the underlying citizen "
                "database becomes very large."
            ),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("4. Where RAG Is Used"),
            h2("Meaning of RAG in This Project"),
            p(
                "<b>Retrieval-Augmented Generation (RAG)</b> means the LLM is not expected to remember or guess "
                "the schema. Before SQL generation, the application retrieves relevant schema knowledge and adds "
                "it to the model prompt."
            ),
            p(
                "This is <b>schema RAG</b>, not record RAG: FAISS stores table/column descriptions and aliases, "
                "not personal citizen data."
            ),
            h2("Retrieval Pipeline"),
            data_table(
                ["Stage", "Implementation", "Example for 'boys above 21 in Jaipur'"],
                [
                    ["Vector recall", "FAISS similarity search", "Likely discovers age, gender, district."],
                    ["Lexical anchors", "Aliases and known Rajasthan districts", "boys -> gender; Jaipur -> district."],
                    ["Domain gates", "Exclude domains unless requested", "No pension, eKYC, bank, or caste columns."],
                    ["Join enrichment", "Include required foreign keys", "member.family_id and family.family_id."],
                    ["Display enrichment", "Name for list queries", "member.member_name."],
                ],
                [3.1 * cm, 5.1 * cm, 7.4 * cm],
            ),
            h2("Pruned Schema Context Example"),
            p(
                "For a demographic/location question, the retrieved context is deliberately compact:"
            ),
            code(
                """
Tables:
  family
  member

Columns:
  family.district
  family.family_id
  member.age
  member.family_id
  member.gender
  member.member_name

Relationship:
  member.family_id = family.family_id
"""
            ),
            p(
                "Columns such as <b>member.caste_category</b>, <b>verification.ekyc_status</b>, and "
                "<b>scheme_benefits.pension_eligibility</b> are withheld unless the question actually requests "
                "those subjects. This reduces prompt size and decreases hallucination opportunities."
            ),
            h2("Why the Architecture Is Hybrid"),
            p(
                "Vector search is strong at meaning and synonyms, but production behavior also needs deterministic "
                "boundaries. The implementation combines vector retrieval with explicit domain gating and pruning. "
                "That provides semantic flexibility while preventing irrelevant sensitive domains from being exposed "
                "to the SQL generator."
            ),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("5. Natural Language Cleanup and Domain Vocabulary"),
            h2("Spelling Correction"),
            p(
                "The <b>normalization/query_normalizer.py</b> module uses RapidFuzz before retrieval. It fixes "
                "likely misspellings of controlled terms and Rajasthan district names, but preserves correctly "
                "written natural language rather than rephrasing it."
            ),
            data_table(
                ["Input Fragment", "Normalized Fragment", "Reason"],
                [
                    ["femail", "female", "Known typo correction"],
                    ["benificiaries", "beneficiaries", "Known typo correction"],
                    ["jaipor", "Jaipur", "District typo correction"],
                    ["female beneficiaries receiving pension", "unchanged", "Valid text must not be rewritten"],
                ],
                [4.3 * cm, 5.2 * cm, 6.1 * cm],
            ),
            h2("Location Handling"),
            p(
                "The metadata includes the 41 Rajasthan districts used by the project. Explicit district aliases "
                "help FAISS and lexical retrieval recognize locations such as Jaipur, Jodhpur, and Bikaner. A "
                "generic fallback also treats text shaped like <b>in &lt;place&gt;</b> or "
                "<b>from &lt;place&gt;</b> as a potential district filter."
            ),
            h2("Business Meaning Versus Physical Schema"),
            p(
                "The column metadata separates the true SQL identifier from its human meaning. This matters when "
                "a legacy production schema contains non-standard or misspelled physical column names."
            ),
            code(
                """
ColumnMeta(
    table="member",
    column="gendr",           # physical database column
    semantic_name="gender",   # clean business meaning
    description="Citizen gender male female other",
    aliases=["gender", "male", "female", "boy", "girl"],
)
"""
            ),
            p(
                "With this setup the embedding index can match the word <b>boys</b> to gender semantics, and the "
                "prompt can correctly tell the LLM that SQL must reference the physical name <b>member.gendr</b>."
            ),
            h1("6. Relational Data Model"),
            p(
                "The demonstration schema is represented in SQLAlchemy and can be created in SQLite. Its design "
                "mirrors the main data domains expected in a Jan Aadhaar-like registry."
            ),
            SchemaRelationshipDiagram(16.5 * cm),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h2("Table Responsibilities"),
            data_table(
                ["Table", "Purpose", "Key Columns Used in Questions"],
                [
                    ["family", "Household and geographic location", "family_id, district, block, village, jan_aadhaar_number"],
                    ["member", "Citizen demographic and identity profile", "member_id, family_id, member_name, age, gender, caste_category"],
                    ["scheme_benefits", "Welfare eligibility and benefit states", "member_id, nfsa_status, pension_eligibility, beneficiary_status"],
                    ["bank_details", "DBT and banking information", "member_id, dbt_status, ifsc_code"],
                    ["verification", "eKYC and seeding states", "member_id, ekyc_status, aadhaar_seeding_status"],
                ],
                [3.0 * cm, 5.0 * cm, 7.6 * cm],
            ),
            h2("Declared Joins"),
            code(
                """
member.family_id          = family.family_id
bank_details.member_id    = member.member_id
scheme_benefits.member_id = member.member_id
verification.member_id    = member.member_id
"""
            ),
            h2("Indexes in the Demo Schema"),
            bullet("<b>ix_family_geo</b>: district, block, gram_panchayat, village."),
            bullet("<b>ix_member_gender_caste_age</b>: gender, caste_category, age."),
            bullet("<b>ix_scheme_pension_beneficiary</b>: pension_eligibility, beneficiary_status."),
            bullet("<b>ix_verification_ekyc_aadhaar</b>: ekyc_status, aadhaar_seeding_status."),
            p(
                "The demo SQLite database is for functionality demonstrations. At production citizen scale, a "
                "server-grade RDBMS or warehouse would replace SQLite while preserving the metadata/retrieval layer."
            ),
            h1("7. Prompt Building and LLM SQL Generation"),
            h2("Role of the LLM"),
            p(
                "The LLM is responsible for composing a SQL SELECT query from the user's intent and the reduced "
                "schema context. It does <b>not</b> choose the entire schema from memory and does <b>not</b> receive "
                "citizen records."
            ),
            data_table(
                ["Setting", "Current Value", "Reason"],
                [
                    ["Generation model", "qwen2.5-coder:3b", "Responsive local default on a laptop"],
                    ["Embedding model", "nomic-embed-text", "Local semantic representation of schema/query"],
                    ["Temperature", "0", "Reduce random variation in SQL"],
                    ["Context window", "2048", "Reduced RAG prompts do not require a large window"],
                    ["Output token cap", "256", "SQL should remain compact"],
                    ["Keep-alive", "30 minutes", "Reduce repeated model reload latency in Streamlit"],
                ],
                [4.0 * cm, 4.3 * cm, 7.3 * cm],
            ),
            h2("Prompt Guardrails"),
            bullet("Generate exactly one read-only SELECT statement."),
            bullet("Use only the supplied tables, columns, and relationships."),
            bullet("Never invent a column or use SELECT *."),
            bullet("Only use caste fields when caste is explicitly requested."),
            bullet("Interpret boy/girl, age comparisons, and district language consistently."),
            p(
                "These are model instructions. They improve generation, but they are not treated as the final "
                "security boundary. The validator is the enforced control."
            ),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("8. Worked Example: From Question to SQL"),
            h2("Question"),
            code("All boys above 21 in Jaipur"),
            h2("Step A: Normalization"),
            p("The sentence is already valid, so it is left unchanged and no correction banner is shown."),
            h2("Step B: Semantic Retrieval and Pruning"),
            code(
                """
family.district
family.family_id
member.age
member.family_id
member.gender
member.member_name
"""
            ),
            h2("Step C: Reduced RAG Prompt"),
            p(
                "The LLM receives only the two relevant tables, the six columns above, the valid relationship "
                "<b>member.family_id = family.family_id</b>, and the user's question."
            ),
            h2("Step D: Generated SQL"),
            code(
                """
SELECT DISTINCT member.member_name
FROM member
JOIN family ON member.family_id = family.family_id
WHERE member.gender = 'Male'
  AND member.age > 21
  AND family.district = 'Jaipur';
"""
            ),
            h2("Step E: Validation"),
            data_table(
                ["Check", "Outcome"],
                [
                    ["Single SQL statement", "Pass"],
                    ["Read-only SELECT only", "Pass"],
                    ["Tables present in retrieved context", "Pass: member, family"],
                    ["Columns present in retrieved context", "Pass"],
                    ["Declared join relationship", "Pass"],
                    ["No dataset modification command", "Pass"],
                ],
                [7.0 * cm, 8.6 * cm],
            ),
            h2("Step F: Optional Planning"),
            p(
                "The UI may request an EXPLAIN QUERY PLAN report. If actual timing is selected, only the already "
                "validated SELECT is executed against the demo database to measure execution behavior."
            ),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("9. SQL Validation and Dataset Safety"),
            p(
                "A text-to-SQL application must treat generated SQL as untrusted output. The validator in "
                "<b>validation/sql_validator.py</b> is positioned after every generation attempt and before "
                "optimization or optional execution."
            ),
            h2("Enforced Read-Only Policy"),
            data_table(
                ["SQL Pattern", "Allowed?", "Reason"],
                [
                    ["SELECT member.member_name FROM member;", "Yes", "Single read-only query"],
                    ["UPDATE member SET age = 18;", "No", "Write statement"],
                    ["DELETE FROM member;", "No", "Deletes records"],
                    ["DROP TABLE member;", "No", "DDL command"],
                    ["SELECT ...; DELETE FROM member;", "No", "Multiple statements and write command"],
                    ["SELECT ... INTO backup_member ...;", "No", "Creates/writes output table"],
                ],
                [7.6 * cm, 2.0 * cm, 6.0 * cm],
            ),
            h2("Other Validation Checks"),
            bullet("Unknown table names are rejected."),
            bullet("Unknown physical columns are rejected."),
            bullet("Columns not retrieved by the RAG context are rejected."),
            bullet("Joins outside declared relationships are rejected."),
            bullet("Qualified column references require that their table be included in FROM or JOIN."),
            bullet("SQL aliases are resolved before join and column validation."),
            h2("Retry Loop"),
            p(
                "If a generated query fails validation, its error is inserted into the next prompt and Qwen is "
                "allowed to regenerate. The application permits at most three attempts. If no valid SQL is produced, "
                "the application returns no usable SQL rather than exposing unsafe output."
            ),
            h2("Safety Boundary Clarification"),
            p(
                "The project currently generates and optionally runs SELECT queries against a demo SQLite database. "
                "For real citizen information, production deployment should also add authorization, sensitive-column "
                "masking, query timeouts, row limits, auditing, and read-only database credentials."
            ),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("10. Optimization and Local Performance"),
            h2("Current Latency Profile"),
            p(
                "FAISS schema search is small and local. The primary runtime cost is local LLM inference through "
                "Ollama. The system currently uses <b>qwen2.5-coder:3b</b> instead of the larger 7B model to favor "
                "laptop responsiveness."
            ),
            h2("Implemented Speed Measures"),
            data_table(
                ["Measure", "How It Helps"],
                [
                    ["Reduced schema context", "Fewer prompt tokens and less SQL confusion."],
                    ["qwen2.5-coder:3b default", "Smaller local generation workload than 7B."],
                    ["num_ctx = 2048", "Avoids reserving excessive context for short SQL prompts."],
                    ["num_predict = 256", "Prevents long unnecessary model output."],
                    ["keep_alive = 30m", "Keeps the model resident during a Streamlit session."],
                    ["Persisted FAISS index", "Schema embeddings are not rebuilt per normal query."],
                ],
                [5.0 * cm, 10.6 * cm],
            ),
            h2("EXPLAIN and Index Recommendations"),
            p(
                "The optimization layer can call SQLite's <b>EXPLAIN QUERY PLAN</b> after SQL is validated. It can "
                "also flag referenced non-indexed columns as candidates for indexing if they are repeatedly used "
                "as filters."
            ),
            h2("Scaling to a Large Citizen Database"),
            bullet("Replace demo SQLite with PostgreSQL, SQL Server, Oracle, or a suitable analytical store."),
            bullet("Run generated SQL with read-only credentials and strict query timeouts."),
            bullet("Use partitioning/indexing strategies for district, block, benefit status, and update dates."),
            bullet("Keep FAISS focused on schema metadata; do not embed sensitive citizen rows for this workflow."),
            bullet("Introduce authorization-aware retrieval so only permitted columns can enter the LLM prompt."),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("11. Interfaces and Operations"),
            h2("Streamlit UI"),
            p(
                "The Streamlit interface provides a question text box, generated SQL display, retrieved tables and "
                "columns, retrieval confidence, execution plan, execution time, spelling corrections, and optional "
                "setup actions."
            ),
            data_table(
                ["Sidebar Control", "Purpose"],
                [
                    ["Pull missing Ollama models", "Allows required local models to be downloaded if absent."],
                    ["Execute generated query for timing", "Executes only validated SELECT SQL for timing."],
                    ["Seed demo database", "Creates and loads the small SQLite demonstration dataset."],
                    ["Rebuild schema index", "Re-embeds schema metadata after aliases/descriptions change."],
                ],
                [5.8 * cm, 9.8 * cm],
            ),
            h2("CLI"),
            code(
                """
python app.py "All boys above 21 in Jaipur"
python app.py --seed-demo-db --build-index "Show pension beneficiaries in Jaipur"
"""
            ),
            h2("When to Rebuild the FAISS Index"),
            bullet("After adding or changing a table or column description."),
            bullet("After adding aliases, district values, or semantic names."),
            bullet("After mapping a legacy physical column name to a business meaning."),
            bullet("Not for each ordinary user query."),
            h1("12. Evaluation and Testing"),
            p(
                "The evaluation module contains benchmark questions and expected SQL. It records exact-match status, "
                "schema accuracy, retrieval accuracy, and latency. Unit tests cover prompt constraints, schema "
                "retrieval/pruning, typo normalization, model detection, and SQL validation safety."
            ),
            data_table(
                ["Evaluation Metric", "Meaning"],
                [
                    ["Exact match", "Whether generated SQL text matches expected normalized SQL exactly."],
                    ["Schema accuracy", "Whether generated SQL passes schema and safety validation."],
                    ["Retrieval accuracy", "Whether required expected columns were included in retrieved context."],
                    ["Latency", "Elapsed runtime for retrieval, generation, validation and planning."],
                ],
                [4.1 * cm, 11.5 * cm],
            ),
            PageBreak(),
        ]
    )

    body.extend(
        [
            h1("13. Codebase Map"),
            data_table(
                ["Path", "Responsibility"],
                [
                    ["app.py", "End-to-end orchestration, retry loop, CLI entry point."],
                    ["config/settings.py", "Models, paths, retry count, retrieval size, Ollama keep-alive."],
                    ["database/models.py", "SQLAlchemy relational models and indexes."],
                    ["database/schema_metadata.py", "Semantic schema documents, aliases, districts, relationships."],
                    ["normalization/query_normalizer.py", "RapidFuzz user-input typo correction."],
                    ["embeddings/ollama_embeddings.py", "Local embedding calls and vector normalization."],
                    ["embeddings/faiss_store.py", "Schema document creation, FAISS build/load/search."],
                    ["retrieval/schema_retriever.py", "Hybrid vector/lexical retrieval and domain pruning."],
                    ["prompting/prompt_builder.py", "Reduced-context SQL generation prompt and guardrails."],
                    ["llm/ollama_client.py", "Ollama model checking/pulling and Qwen generation."],
                    ["validation/sql_validator.py", "Read-only policy and schema/join/context validation."],
                    ["optimization/query_optimizer.py", "Validated EXPLAIN, timing, index recommendations."],
                    ["ui/streamlit_app.py", "Browser interface for questions and results."],
                    ["evaluation/benchmark.py", "Benchmark execution and result metrics."],
                ],
                [5.2 * cm, 10.4 * cm],
            ),
            h1("14. Glossary"),
            data_table(
                ["Term", "Meaning in This System"],
                [
                    ["Embedding", "Numeric meaning representation of a schema document or user question."],
                    ["FAISS", "Local vector similarity index used to search schema metadata."],
                    ["RAG", "Retrieving schema knowledge before asking the LLM to generate SQL."],
                    ["LLM", "Qwen model that composes SQL from question plus retrieved schema context."],
                    ["Semantic metadata", "Column/table description, aliases, sample values, and business meaning."],
                    ["Pruning", "Removal of unrelated retrieved columns before prompting the LLM."],
                    ["Validation", "Enforced check that SQL is read-only and uses permitted schema."],
                    ["EXPLAIN", "Database-generated description of how a validated query would be executed."],
                ],
                [3.3 * cm, 12.3 * cm],
            ),
            Spacer(1, 0.5 * cm),
            h2("Summary"),
            p(
                "The project is a local, retrieval-first Text-to-SQL application. Its central idea is that a "
                "language model generates better and safer SQL when it receives a carefully retrieved slice of "
                "schema knowledge rather than the full database design. Embeddings and FAISS locate that knowledge, "
                "RAG passes it into the prompt, Qwen writes SQL, and deterministic validation decides whether the "
                "SQL is safe enough to display or execute."
            ),
        ]
    )
    return body


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.65 * cm,
        title="Jan Aadhaar NL2SQL Project Guide",
        author="Codex",
    )
    document.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
