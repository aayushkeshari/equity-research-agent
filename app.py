from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "src"))

from equity_research.config import Settings
from equity_research.pipeline import run_research
from equity_research.report import json_report, markdown_report
from equity_research.sec_client import SECClient

load_dotenv()
st.set_page_config(page_title="Equity Research Agent", page_icon="📈", layout="wide")

st.title("Equity Research Agent")
st.caption("Evidence-first SEC filing + XBRL change detection")

with st.sidebar:
    ticker = st.text_input("Ticker", value="NVDA").upper().strip()
    form = st.selectbox("Filing type", ["10-Q", "10-K"])
    use_llm = st.checkbox("Optional AI synthesis", value=False)
    st.info("The deterministic filing/XBRL pipeline works without an LLM API key.")
    run = st.button("Run research", type="primary", use_container_width=True)

if run:
    try:
        settings = Settings.from_env()
        client = SECClient(settings.sec_user_agent, cache_dir=settings.cache_dir)
        with st.spinner("Retrieving SEC filings and Company Facts..."):
            bundle = run_research(
                client,
                ticker=ticker,
                form=form,
                use_llm=use_llm,
                openai_api_key=settings.openai_api_key,
                openai_model=settings.openai_model,
            )
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    st.subheader(f"{bundle.company_name} ({bundle.ticker})")
    c1, c2, c3 = st.columns(3)
    c1.metric("Current report date", bundle.current_filing.report_date)
    c2.metric("Prior report date", bundle.prior_filing.report_date)
    c3.metric("Research leads", len(bundle.leads))

    st.subheader("Financial snapshot")
    rows = []
    for metric, fact in bundle.current_financials.facts.items():
        prior = bundle.prior_financials.facts.get(metric)
        rows.append({
            "Metric": fact.label,
            "Current": fact.value,
            "Prior": prior.value if prior else None,
            "Change %": ((fact.value-prior.value)/abs(prior.value)) if prior and prior.value else None,
            "XBRL concept": fact.concept,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if bundle.llm_summary:
        st.subheader("Evidence-constrained AI synthesis")
        st.write(bundle.llm_summary.get("executive_summary", ""))
        for item in bundle.llm_summary.get("priority_leads", []):
            with st.expander(item.get("theme", "Lead")):
                st.write(item.get("why_it_matters", ""))
                st.write("**Question:**", item.get("follow_up_question", ""))
                st.write("**Evidence IDs:**", ", ".join(item.get("evidence_ids", [])))

    st.subheader("Research leads")
    for lead in bundle.leads:
        with st.expander(f"[{lead.category}] {lead.title} — score {lead.score:.1f}"):
            st.write(lead.rationale)
            if lead.analyst_question:
                st.write("**Question to investigate:**", lead.analyst_question)
            if lead.metrics:
                st.json(lead.metrics)
            for ev in lead.evidence:
                st.markdown(f"**{ev.evidence_id} · {ev.period} · {ev.label}**")
                st.write(ev.excerpt)

    md = markdown_report(bundle)
    js = json_report(bundle)
    d1, d2 = st.columns(2)
    d1.download_button("Download Markdown", md, file_name=f"{ticker.lower()}_research.md")
    d2.download_button("Download JSON", js, file_name=f"{ticker.lower()}_research.json")
