# miniNova — Trade Document Validator

I built this for the GoComet Nova take-home. The idea is simple: you upload a trade document (Bill of Lading, commercial invoice, whatever), and three agents work through it — one pulls out the fields, one checks them against what the customer expects, and one decides what to do next. Auto-approve, flag it, or write up an amendment request.

It actually works. I tested it on real PDFs and scanned images and the results are solid.

---

## What it does

**Three agents running in sequence via LangGraph:**

1. **Extractor** — sends the document to Llama 4 Scout (vision-capable), gets back structured JSON with 8 fields and a confidence score for each one
2. **Validator** — compares every field against the customer's rule set. Supports fuzzy matching, exact matching, and prefix matching. Ports like "JNPT Nhava Sheva" correctly match "JNPT Mumbai". Incoterms like "CIF (Cost, Insurance & Freight)" correctly match "CIF".
3. **Decision Agent** — reads the validation output and picks one of three outcomes. If anything is uncertain, it flags for human review first (before even checking for mismatches). If there are mismatches, it drafts a field-by-field amendment request. If everything checks out, it auto-approves. The LLM explains *why* it made the decision — not just what the decision is.

Everything gets saved to SQLite. There's a natural language query box at the bottom — you can type "how many shipments were flagged this week?" and it'll actually answer.

---

## Project structure

```
miniNova/
├── app.py              # Streamlit UI — the whole frontend
├── graph.py            # LangGraph pipeline definition
├── config.py           # Customer rule set (GlobalTech Imports GmbH)
├── rag.py              # TF-IDF retrieval for relevant compliance rules
├── requirements.txt
│
├── agents/
│   ├── extractor.py    # Vision + text extraction with retry logic
│   ├── validator.py    # Fuzzy/exact/prefix matching against rules
│   └── decision.py     # Priority logic + LLM reasoning
│
├── core/
│   ├── llm.py          # Groq API wrapper (text + vision calls)
│   └── parser.py       # JSON cleaning utilities
│
└── db/
    └── database.py     # SQLite persistence + NL query layer
```

---

## Getting it running

### 1. Clone the repo

```bash
git clone https://github.com/annssshhhh01/miniNova.git
cd miniNova
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** All dependencies are pure Python — no C extensions, no compiled libraries. This was intentional. It runs on restricted corporate environments where native DLLs get blocked.

### 4. Add your Groq API key

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com/keys](https://console.groq.com/keys). The free tier is more than enough for testing.

### 5. Run it

```bash
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## How to test it

Upload any trade document PDF or image. The pipeline runs and shows:

- **Extracted fields table** — 8 fields, each with a value and confidence score (🟢 high / 🟡 medium / 🔴 low)
- **Validation results table** — expected vs found for every field, with match/mismatch/uncertain status
- **Decision banner** — auto_approve / flag_for_review / amendment_required with the agent's reasoning
- **Amendment request** — if mismatches found, lists every discrepancy with the corrective action
- **Flagged fields** — if anything is uncertain, it surfaces here — never silently approved
- **Dashboard stats** — running counts of approved / flagged / amendments across all runs
- **NL query** — ask questions in plain English about your stored data

### Three document scenarios worth testing

| Document | What should happen |
|---|---|
| Clean document — all fields match | 🟢 auto_approve |
| Degraded/scanned — some fields unreadable | 🟡 flag_for_review |
| Messy doc — wrong Incoterms (FOB instead of CIF) | 🔴 amendment_required |

---

## The customer rule set

I defined rules for one customer: **GlobalTech Imports GmbH** (CUST001). The rules live in `config.py` and cover all 8 fields:

| Field | Expected | Match Type |
|---|---|---|
| Consignee Name | GlobalTech Imports GmbH | Fuzzy |
| HS Code | 8471.30 | Exact |
| Port of Loading | JNPT Mumbai | Fuzzy + variants |
| Port of Discharge | Hamburg | Fuzzy + variants |
| Incoterms | CIF | Code extraction |
| Description of Goods | Electronic Components | Fuzzy (contains) |
| Gross Weight | 500 KG | Fuzzy |
| Invoice Number | INV prefix | Prefix match |

To change the customer or rules, edit `config.py`. No database migration needed.

---

## The RAG component

The decision agent uses RAG to pull relevant compliance rules before generating its reasoning. I implemented it in pure Python using TF-IDF + cosine similarity — no sentence-transformers, no FAISS, no vector database. It's not glamorous but it's fast, it works offline, and it doesn't require any native libraries.

The rule corpus is in `rag.py`. The retriever finds the top-2 most relevant rules for the current validation state and passes them to the LLM as context.

---

## Model

Everything runs on **`meta-llama/llama-4-scout-17b-16e-instruct`** via Groq. It handles both text prompts (extraction, decision reasoning) and vision input (direct image uploads).

For PDFs — text is extracted via `pypdf` and sent to the text endpoint. For images — the file is base64-encoded and sent to the vision endpoint. If vision extraction fails, it falls back to text.

---

## Known limitations

- **Scanned PDFs** — pypdf extracts text from text-based PDFs fine. If the PDF is a scan (no text layer), you'll get better results uploading the pages as images directly.
- **Rule set** — currently hardcoded for one customer. Multi-tenant rule management would be the obvious next step.
- **RAG quality** — TF-IDF works but misses semantic similarity. A proper embedding model would improve retrieval accuracy significantly.
- **No async** — the pipeline is synchronous. For bulk processing, you'd want to run extractions in parallel.

---

## Stack

- **LangGraph** — pipeline orchestration and state management
- **Groq + Llama 4 Scout** — extraction and decision reasoning
- **Streamlit** — UI
- **SQLite** — persistence
- **pypdf** — PDF text extraction
- **Pure Python TF-IDF** — RAG retrieval

No Docker needed. No database server. Just Python and a Groq API key.
