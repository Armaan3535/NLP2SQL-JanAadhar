from __future__ import annotations

import streamlit as st

from app import generate_sql_pipeline
from database.excel_importer import import_excel_dataset
from database.query_results import execute_select_preview
from database.sample_data import seed_demo_data
from embeddings.faiss_store import FaissSchemaStore


def render() -> None:
    st.set_page_config(page_title="Jan Aadhaar NL2SQL", layout="wide")
    st.title("Jan Aadhaar NL2SQL")

    with st.sidebar:
        st.header("Local Setup")
        auto_pull = st.checkbox("Pull missing Ollama models", value=False)
        run_profile = st.checkbox("Execute generated query for timing", value=False)
        show_results = st.checkbox("Show matching entries", value=True)
        result_limit = st.number_input("Maximum displayed rows", min_value=10, max_value=1000, value=200, step=10)
        if st.button("Seed demo database"):
            seed_demo_data()
            st.success("Demo database is ready.")
        uploaded_data = st.file_uploader("Import dummy Excel dataset", type=["xlsx"])
        if uploaded_data is not None and st.button("Load uploaded dataset"):
            with st.spinner("Loading records into the local SQLite database..."):
                try:
                    report = import_excel_dataset(uploaded_data, uploaded_data.name)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Loaded {report.members_loaded} citizen records.")
                    st.caption("No welfare or verification fields exist in this workbook; those tables remain empty.")
        if st.button("Rebuild schema index"):
            with st.spinner("Embedding schema metadata with Ollama and rebuilding FAISS..."):
                FaissSchemaStore().build(force=True)
            st.success("Schema index rebuilt.")

    question = st.text_area(
        "Natural language question",
        value="Show all boys above 21 in Jaipur.",
        height=100,
    )
    if st.button("Generate SQL", type="primary"):
        with st.spinner("Retrieving schema context and generating SQL locally..."):
            try:
                output = generate_sql_pipeline(
                    question,
                    ask_model_pull=auto_pull,
                    include_optimization=True,
                    run_query_for_profile=run_profile,
                )
            except Exception as exc:
                st.error(str(exc))
                return

        st.subheader("Generated SQL")
        st.code(output.sql, language="sql")

        c1, c2, c3 = st.columns(3)
        c1.metric("Confidence", output.confidence)
        c2.metric("Retrieved tables", len(output.retrieved_tables))
        c3.metric("Retrieved columns", len(output.retrieved_columns))

        if output.query_corrections:
            st.subheader("Query Corrections")
            st.write(output.query_corrections)
            st.caption(f"Normalized question: {output.normalized_question}")

        left, right = st.columns(2)
        with left:
            st.subheader("Retrieved Tables")
            st.write(output.retrieved_tables)
        with right:
            st.subheader("Retrieved Columns")
            st.write(output.retrieved_columns)

        if output.validation_errors:
            st.subheader("Validation Errors")
            st.error("; ".join(output.validation_errors))

        if show_results and output.sql:
            st.subheader("Matching Entries")
            try:
                preview = execute_select_preview(output.sql, max_rows=int(result_limit))
            except Exception as exc:
                st.error(f"Results could not be displayed: {exc}")
            else:
                if preview.rows.empty:
                    st.info("The query returned no matching entries in the currently loaded dataset.")
                else:
                    st.dataframe(preview.rows, width="stretch", hide_index=True)
                    st.caption(
                        f"Showing {preview.displayed_rows} matching row(s)"
                        + ("; more rows exist." if preview.truncated else ".")
                    )
                    st.download_button(
                        "Download displayed results as CSV",
                        data=preview.rows.to_csv(index=False).encode("utf-8"),
                        file_name="query_results_preview.csv",
                        mime="text/csv",
                    )

        if output.optimization:
            st.subheader("Execution Plan")
            st.code("\n".join(output.optimization.execution_plan))
            st.metric("Planning / execution time", f"{output.optimization.execution_time_ms} ms")
            if output.optimization.index_recommendations:
                st.subheader("Index Recommendations")
                st.write(output.optimization.index_recommendations)
