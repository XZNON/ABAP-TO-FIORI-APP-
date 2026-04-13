# SAP Fiori RAG Analyzer

Analyzes a custom ABAP report and finds the closest matching standard SAP Fiori
app using Retrieval-Augmented Generation.

**Stack:** LangChain · Groq (llama-3.3-70b) · ChromaDB · sentence-transformers

---

## How it works

```
ABAP file
   │
   ▼
[Chain 1 — Groq]          Parse code → plain-language functional summary
   │
   ▼
[ChromaDB similarity]     Embed summary → cosine search over ~3,500 Fiori apps
   │
   ▼
[Chain 2 — Groq]          Re-rank top-k results → BEST MATCH + GAPS + RECOMMENDATION
   │
   ▼
Console output
```

---

## Setup

### 1. Clone / copy the project

```bash
cd sap_rag
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> First run downloads the `all-MiniLM-L6-v2` embedding model (~80 MB) from
> HuggingFace and caches it locally. No API key needed for embeddings.

### 4. Set your Groq API key

Get a free key at **https://console.groq.com** → API Keys.

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY=gsk_your-key-here
```

Or export directly:

```bash
export GROQ_API_KEY=gsk_your-key-here
```

---

## Usage

### Basic run

```bash
python main.py --file path/to/ZFIN_VENDOR_AGING.abap
```

### Rebuild the Fiori app index (re-crawl)

```bash
python main.py --file ZFIN_VENDOR_AGING.abap --rebuild-index
```

### Show more matches

```bash
python main.py --file ZFIN_VENDOR_AGING.abap --top-k 8
```

---

## Project structure

```
sap_rag/
├── main.py                     Entry point
├── requirements.txt
├── .env.example
│
├── crawler/
│   └── fiori_crawler.py        Crawls SAP Fiori Apps Library OData API
│                               Falls back to curated seed corpus (FI-AP focused)
│
├── vectordb/
│   └── store.py                ChromaDB wrapper — build / load / search
│
├── rag/
│   └── analyzer.py             Two LangChain chains (summarizer + re-ranker)
│                               Both use Grok via openai_api_base override
│
└── data/
    ├── fiori_apps_cache.json   Cached crawl results (auto-created)
    └── chroma_db/              Persisted vector index (auto-created)
```

---

## Groq + LangChain integration

Groq's API is OpenAI-compatible. The only change needed is overriding
`openai_api_base` and using your `gsk_...` key:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",   # or llama-3.1-8b-instant for speed
    openai_api_key="gsk_your-key",
    openai_api_base="https://api.groq.com/openai/v1",
    temperature=0,
)
```

Available Groq models you can swap into `rag/analyzer.py`:

| Model                     | Context | Best for                |
| ------------------------- | ------- | ----------------------- |
| `llama-3.3-70b-versatile` | 128k    | Best quality (default)  |
| `llama-3.1-8b-instant`    | 128k    | Fastest, lowest cost    |
| `mixtral-8x7b-32768`      | 32k     | Long ABAP files         |
| `gemma2-9b-it`            | 8k      | Lightweight alternative |

---

## Extending the corpus

To add more apps to the seed corpus, edit `crawler/fiori_crawler.py` and
append entries to the `SEED_APPS` list. Each entry needs:

```python
{
    "app_id": "F1234",
    "title": "...",
    "description": "...",
    "app_type": "Analytical / Transactional / ...",
    "product": "S/4HANA Finance",
    "business_role": "...",
    "tags": ["FI-AP", "..."],
}
```

Then run with `--rebuild-index` to re-embed.

---

## Example output

```
============================================================
  SAP Fiori RAG Analyzer — powered by Grok + LangChain
============================================================

[1/3] Loading existing vector index...

[2/3] Parsing ABAP code with Grok...
      Summary: This report serves the accounts payable month-end close...

[3/3] Results

  Functional summary:
  This report serves the accounts payable process within the FI-AP
  module of SAP ERP. It reads open vendor invoices from the BSIK table
  ...

  Top 5 matching SAP standard apps:
  --------------------------------------------------------
  1. [94%] Supplier Aging Report
       App ID : F2697
       Desc   : Detailed supplier aging report with configurable bucket...

  2. [91%] Accounts Payable Aging
       App ID : F2680
       ...

  Recommendation:
  BEST MATCH: F2697 — Supplier Aging Report
  WHY: Identical aging bucket structure (current, 1-30, 31-60...),
       same key date parameter, same BSIK/BSAK data source.
  GAPS: Custom report uses REUSE_ALV_GRID — F2697 uses Fiori UX (verify AP team preference)
  RECOMMENDATION: REUSE — decommission ZFIN_VENDOR_AGING after parallel run validation.
```
