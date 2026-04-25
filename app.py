import io
import base64
import streamlit as st

from graph import graph
from db.database import init_db, save_result, count_flagged, count_by_decision, query_nl

# Init DB once
init_db()

st.set_page_config(page_title="GoComet Nova · Trade Document Validator", page_icon="📦", layout="wide")

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📦 GoComet Nova — Trade Document Validator")
st.caption("Multi-agent system: **Extractor → Validator → Decision** powered by LangGraph + Groq Vision LLM")
st.divider()

# ── Input ──────────────────────────────────────────────────────────────────────
col_input, col_output = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("📄 Upload Document")

    document_text = ""
    page_images = []  # base64-encoded page images

    uploaded = st.file_uploader("Upload trade document", type=["pdf", "png", "jpg", "jpeg"])
    if uploaded:
        if uploaded.type == "application/pdf":
            try:
                import pypdf
                pdf_bytes = uploaded.read()
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                text_parts = [page.extract_text() or "" for page in reader.pages]
                document_text = "\n".join(text_parts)
                # No page images from PDF (DLL blocked) — text extraction only
                st.success(f"✅ PDF loaded — {len(reader.pages)} page(s) (text extracted)")
            except Exception as e:
                st.error(f"Failed to read PDF: {e}")

        elif uploaded.type in ("image/png", "image/jpeg"):
            img_bytes = uploaded.read()
            page_images.append(base64.b64encode(img_bytes).decode("utf-8"))
            st.image(img_bytes, caption=uploaded.name, use_column_width=True)
            st.success("✅ Image loaded — will use vision LLM for extraction")

        if document_text:
            with st.expander("Preview extracted text"):
                st.text(document_text[:2000] + ("..." if len(document_text) > 2000 else ""))

    run_btn = st.button("⚡ Run Pipeline", type="primary", use_container_width=True)

# ── Pipeline execution ─────────────────────────────────────────────────────────
with col_output:
    st.subheader("📊 Pipeline Results")

    if run_btn:
        if not document_text.strip() and not page_images:
            st.warning("Please upload a document before running.")
        else:
            with st.spinner("Running multi-agent pipeline..."):
                try:
                    result = graph.invoke({
                        "text": document_text,
                        "images": page_images,
                    })
                except Exception as e:
                    st.error(f"Pipeline failed: {e}")
                    st.stop()

            # Save to DB
            save_result(
                result.get("extracted", {}),
                result.get("validated", {}),
                result.get("decision", {}),
            )

            extracted = result.get("extracted", {})
            validated = result.get("validated", {})
            decision = result.get("decision", {})

            # ── Decision Banner ────────────────────────────────────────────
            decision_label = decision.get("decision", "N/A")
            color_map = {
                "auto_approve": "🟢",
                "flag_for_review": "🟡",
                "amendment_required": "🔴",
            }
            icon = color_map.get(decision_label, "⚪")
            st.markdown(f"### {icon} Decision: `{decision_label}`")
            st.info(f"**Reasoning:** {decision.get('reason', 'N/A')}")

            # ── Extracted Fields Table ─────────────────────────────────────
            st.subheader("🔍 Extracted Fields")
            extract_rows = []
            for field, data in extracted.items():
                if isinstance(data, dict):
                    conf = data.get("confidence", 0.0)
                    extract_rows.append({
                        "Field": field.replace("_", " ").title(),
                        "Value": data.get("value", "—"),
                        "Confidence": f"{conf:.0%}",
                        "": "🟢" if conf >= 0.7 else "🟡" if conf >= 0.4 else "🔴",
                    })
            if extract_rows:
                html = '<table style="width:100%; border-collapse:collapse;">'
                html += '<tr style="background:#1e293b;"><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Field</th><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Value</th><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Confidence</th><th style="padding:8px; border-bottom:1px solid #334155;"></th></tr>'
                for row in extract_rows:
                    html += f'<tr><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Field"]}</td><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Value"]}</td><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Confidence"]}</td><td style="padding:8px; border-bottom:1px solid #1e293b;">{row[""]}</td></tr>'
                html += '</table>'
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.json(extracted)

            # ── Validation Results Table ───────────────────────────────────
            st.subheader("✅ Validation Results")
            valid_rows = []
            for field, data in validated.items():
                status = data.get("status", "—")
                status_icon = {"match": "✅ match", "mismatch": "❌ mismatch", "uncertain": "⚠️ uncertain"}.get(status, status)
                valid_rows.append({
                    "Field": field.replace("_", " ").title(),
                    "Expected": data.get("expected", "—"),
                    "Found": data.get("found", "—"),
                    "Status": status_icon,
                    "Confidence": f"{data.get('confidence', 0.0):.0%}",
                })
            if valid_rows:
                html = '<table style="width:100%; border-collapse:collapse;">'
                html += '<tr style="background:#1e293b;"><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Field</th><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Expected</th><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Found</th><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Status</th><th style="padding:8px; text-align:left; border-bottom:1px solid #334155;">Confidence</th></tr>'
                for row in valid_rows:
                    html += f'<tr><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Field"]}</td><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Expected"]}</td><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Found"]}</td><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Status"]}</td><td style="padding:8px; border-bottom:1px solid #1e293b;">{row["Confidence"]}</td></tr>'
                html += '</table>'
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.json(validated)

            # ── Amendment Draft ────────────────────────────────────────────
            if "amendment_draft" in decision and decision["amendment_draft"]:
                st.subheader("📝 Amendment Request")
                for item in decision["amendment_draft"]:
                    st.warning(f"**{item['field'].replace('_', ' ').title()}**: "
                               f"Found `{item['found']}` → Expected `{item['expected']}`\n\n"
                               f"↳ {item['action']}")

            # ── Flagged Fields ─────────────────────────────────────────────
            if "flagged_fields" in decision and decision["flagged_fields"]:
                st.subheader("🚩 Flagged for Human Review")
                for item in decision["flagged_fields"]:
                    st.warning(f"**{item['field'].replace('_', ' ').title()}**: {item['reason']}")

    else:
        st.markdown(
            "<div style='text-align:center; color:#94a3b8; padding:100px 0;'>"
            "Upload a document and click <b>Run Pipeline</b> to see results."
            "</div>",
            unsafe_allow_html=True,
        )

# ── Stats + NL Query ──────────────────────────────────────────────────────────
st.divider()
col_stats, col_query = st.columns([1, 1], gap="large")

with col_stats:
    st.subheader("📊 Dashboard Stats")
    stats = count_by_decision()
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Approved", stats.get("auto_approve", 0))
    c2.metric("🟡 Flagged", stats.get("flag_for_review", 0))
    c3.metric("🔴 Amendment", stats.get("amendment_required", 0))

with col_query:
    st.subheader("💬 Ask About Your Data")
    st.caption("Natural language query over stored results")
    nl_question = st.text_input("Your question", placeholder='e.g. "How many shipments were flagged this week?"')
    if nl_question:
        with st.spinner("Querying..."):
            answer = query_nl(nl_question)
        st.code(answer)
