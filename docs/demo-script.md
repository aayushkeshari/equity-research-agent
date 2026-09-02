# 90-second demo script

I built an evidence-first equity-research pipeline around SEC filings. Instead of asking an LLM to summarize a 10-Q, the system first retrieves two comparable filings and the company's SEC XBRL Company Facts.

The filing side extracts sections such as MD&A and Risk Factors and identifies changes in themes like AI infrastructure, capex, competition, regulation, and supply constraints.

In parallel, the XBRL side normalizes multiple US-GAAP concept names into research metrics such as revenue, R&D, capex, operating cash flow, and margins. It then compares the current and prior reporting periods and calculates derived metrics such as capex intensity and free cash flow.

Every research lead carries provenance back to an exact filing excerpt or XBRL concept. Only after the evidence exists can an optional LLM rank the leads and formulate analyst follow-up questions. The model is not allowed to invent financial facts or unsupported causal explanations.

The main design goal was to move from 'summarize this filing' to 'show me what changed, why it may deserve attention, and where the evidence is.'
