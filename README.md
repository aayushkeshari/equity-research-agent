# Equity Research Agent

Evidence-first AI research infrastructure for public-company SEC filings.

The system is built around a simple investment-research question:

> **What changed, why might it matter, and what exact evidence supports it?**

Unlike a filing summarizer, this project separates **source retrieval**, **structured financial facts**, **deterministic change detection**, and **optional LLM interpretation**. Every surfaced research lead keeps provenance back to the filing or XBRL fact that produced it.

## What it does

### Filing intelligence
- Resolves a ticker to an SEC CIK.
- Pulls recent 10-K / 10-Q filing metadata from EDGAR.
- Downloads and caches filing HTML.
- Normalizes text and extracts common sections such as MD&A and Risk Factors.
- Compares consecutive reporting periods.
- Detects changes in discussion around AI infrastructure, capex, cloud/software, profitability, competition, regulation, cybersecurity, supply constraints, and other research themes.

### XBRL financial intelligence
- Pulls SEC Company Facts from `data.sec.gov/api/xbrl/companyfacts/`.
- Normalizes common US-GAAP concepts across multiple possible taxonomy tags.
- Extracts period-matched values for:
  - revenue
  - gross profit
  - operating income
  - net income
  - R&D
  - capex
  - operating cash flow
  - cash
  - total assets
  - total liabilities
- Computes derived metrics including gross margin, operating margin, net margin, capex intensity, R&D intensity, and free cash flow.
- Compares the latest period with the previous comparable period and surfaces material changes.

### Evidence-first research leads
Each lead contains:
- theme
- title
- signal score
- rationale
- deterministic metrics
- exact text excerpts and/or XBRL facts
- SEC accession / filing provenance

### Optional LLM synthesis
If `OPENAI_API_KEY` is configured, the project can ask a model to rank the deterministic leads and produce analyst-style questions. The model receives evidence IDs and is instructed not to introduce unsupported claims.

### Outputs
- terminal report
- Markdown report
- JSON research bundle
- Streamlit dashboard

---

## Architecture

```text
                         +----------------------+
                         |      SEC EDGAR       |
                         +-----------+----------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
     Filing submissions API                         Company Facts API
              |                                             |
              v                                             v
       Filing HTML cache                           XBRL normalization
              |                                             |
              v                                             v
     HTML -> clean text                           Period/value alignment
              |                                             |
              v                                             v
      Section extraction                         Derived financial metrics
              |                                             |
              +----------------------+----------------------+
                                     |
                                     v
                              Signal engine
                                     |
                         +-----------+-----------+
                         |                       |
                         v                       v
                  Textual changes          Financial changes
                         |                       |
                         +-----------+-----------+
                                     |
                                     v
                          Evidence-backed leads
                                     |
                                     v
                         Optional LLM synthesis
                                     |
                   +-----------------+------------------+
                   |                                    |
                   v                                    v
             Markdown / JSON                       Streamlit UI
```

## Design principle

The LLM is **not** the source of truth.

A final claim should be reconstructable from:
1. filing accession number,
2. filing/report date,
3. filing section or XBRL concept,
4. exact excerpt or numeric fact,
5. deterministic comparison features,
6. optional model interpretation.

---

## Setup

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set an identifying SEC user agent in `.env`:

```env
SEC_USER_AGENT="Your Name your-email@example.com"
```

Optional LLM synthesis:

```env
OPENAI_API_KEY="..."
OPENAI_MODEL="gpt-5-mini"
```

## Run

### Full research pipeline

```bash
PYTHONPATH=src python -m equity_research.cli research NVDA --form 10-Q
```

Write both Markdown and JSON:

```bash
PYTHONPATH=src python -m equity_research.cli research NVDA \
  --form 10-Q \
  --markdown reports/nvda.md \
  --json reports/nvda.json
```

Add optional LLM synthesis:

```bash
PYTHONPATH=src python -m equity_research.cli research NVDA --form 10-Q --llm
```

### Financial facts only

```bash
PYTHONPATH=src python -m equity_research.cli financials MSFT --form 10-Q
```

### Streamlit dashboard

```bash
streamlit run app.py
```

---

## What the output means

A signal is a **research lead**, not an investment recommendation. For example:

```text
Research lead: Capex intensity increased

Current period:
  Capital expenditures: $14.9B
  Revenue: $82.0B
  Capex intensity: 18.2%

Comparison period:
  Capital expenditures: $9.5B
  Revenue: $67.4B
  Capex intensity: 14.1%

Change:
  +4.1 percentage points

Potential analyst question:
  Is incremental infrastructure investment leading demand, responding to
  capacity constraints, or changing the expected return profile of growth?

Evidence:
  XBRL us-gaap:PaymentsToAcquirePropertyPlantAndEquipment
  XBRL us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax
  SEC filing accession ...
```

---

## Project structure

```text
src/equity_research/
  analyzer.py       textual change signals
  cli.py            command-line interface
  config.py         settings
  financials.py     XBRL normalization and comparison
  llm.py            optional evidence-constrained synthesis
  models.py         typed domain objects
  parser.py         filing HTML / section extraction
  pipeline.py       end-to-end orchestration
  report.py         Markdown / JSON output
  sec_client.py     EDGAR client and caching
app.py              Streamlit dashboard
tests/              offline unit tests
```

## Roadmap

The repo already contains the complete portfolio MVP. Natural extensions include:
- semantic embeddings for sentence-level change retrieval,
- transcript / earnings-call ingestion,
- cross-company thematic screens,
- analyst-labelled evaluation sets,
- vector database or SQLite run history,
- event-driven monitoring for newly filed 10-Q/10-Ks,
- richer valuation / consensus data from licensed sources.

## Data-source note

SEC `data.sec.gov` APIs provide public company submissions and extracted XBRL facts without an API key. Automated access should identify the requester, cache responses, and avoid aggressive request rates.
