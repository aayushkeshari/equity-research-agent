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


def _duration_days(fact):
    if not fact or not fact.start:
        return None
    from datetime import date
    return (date.fromisoformat(fact.end) - date.fromisoformat(fact.start)).days


def _period_label(fact):
    if not fact:
        return "—"
    days = _duration_days(fact)
    return f"{fact.start} → {fact.end} ({days}d)" if days is not None else f"As of {fact.end}"


def _format_change(current, prior):
    if not prior or not prior.value:
        return "—"
    # Only show a change when duration facts have comparable spans.
    cur_days, prior_days = _duration_days(current), _duration_days(prior)
    if (cur_days is None) != (prior_days is None):
        return "Not comparable"
    if cur_days is not None and abs(cur_days - prior_days) > 7:
        return "Not comparable"
    return f"{((current.value-prior.value)/abs(prior.value)):+.1%}"

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
            "Current period": _period_label(fact),
            "Prior": prior.value if prior else None,
            "Prior period": _period_label(prior),
            "Change": _format_change(fact, prior),
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
                if ev.source_type == "xbrl" and ev.metadata:
                    start = ev.metadata.get("start")
                    end = ev.metadata.get("end")
                    days = ev.metadata.get("duration_days")
                    if start:
                        st.caption(f"XBRL period: {start} → {end} ({days} days)")
                    else:
                        st.caption(f"XBRL instant: {end}")

    md = markdown_report(bundle)
    js = json_report(bundle)
    d1, d2 = st.columns(2)
    d1.download_button("Download Markdown", md, file_name=f"{ticker.lower()}_research.md")
    d2.download_button("Download JSON", js, file_name=f"{ticker.lower()}_research.json")
