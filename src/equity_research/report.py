from __future__ import annotations

import json
from dataclasses import asdict

from .models import FinancialPeriod, ResearchBundle


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    n = abs(value)
    if n >= 1e12:
        return f"{sign}${n/1e12:.2f}T"
    if n >= 1e9:
        return f"{sign}${n/1e9:.2f}B"
    if n >= 1e6:
        return f"{sign}${n/1e6:.2f}M"
    return f"{sign}${n:,.0f}"


def _financial_table(current: FinancialPeriod, prior: FinancialPeriod) -> list[str]:
    lines = [
        "| Metric | Current | Prior | Change |",
        "|---|---:|---:|---:|",
    ]
    ordered = [
        "revenue", "gross_profit", "operating_income", "net_income",
        "research_and_development", "capex", "operating_cash_flow", "cash",
    ]
    for metric in ordered:
        c, p = current.facts.get(metric), prior.facts.get(metric)
        if not c or not p:
            continue
        change = "n/a" if p.value == 0 else f"{(c.value-p.value)/abs(p.value):+.1%}"
        lines.append(f"| {c.label} | {_money(c.value)} | {_money(p.value)} | {change} |")

    ratio_labels = {
        "gross_margin": "Gross Margin",
        "operating_margin": "Operating Margin",
        "net_margin": "Net Margin",
        "rnd_intensity": "R&D / Revenue",
        "capex_intensity": "Capex / Revenue",
    }
    for metric, label in ratio_labels.items():
        if metric in current.derived and metric in prior.derived:
            c, p = current.derived[metric], prior.derived[metric]
            lines.append(f"| {label} | {c:.1%} | {p:.1%} | {c-p:+.1%} pts |")

    if "free_cash_flow" in current.derived and "free_cash_flow" in prior.derived:
        c, p = current.derived["free_cash_flow"], prior.derived["free_cash_flow"]
        change = "n/a" if p == 0 else f"{(c-p)/abs(p):+.1%}"
        lines.append(f"| Free Cash Flow | {_money(c)} | {_money(p)} | {change} |")
    return lines


def markdown_report(bundle: ResearchBundle) -> str:
    out: list[str] = []
    out.append(f"# {bundle.company_name} ({bundle.ticker}) Research Brief")
    out.append("")
    out.append("> Machine-generated research leads for analyst review; not investment advice.")
    out.append("")
    out.append("## Filing Comparison")
    out.append("")
    out.append(
        f"- **Current:** {bundle.current_filing.form} — report date "
        f"{bundle.current_filing.report_date}, filed {bundle.current_filing.filing_date}, "
        f"accession `{bundle.current_filing.accession_number}`"
    )
    out.append(f"  - Source: {bundle.current_filing.url}")
    out.append(
        f"- **Prior:** {bundle.prior_filing.form} — report date "
        f"{bundle.prior_filing.report_date}, filed {bundle.prior_filing.filing_date}, "
        f"accession `{bundle.prior_filing.accession_number}`"
    )
    out.append(f"  - Source: {bundle.prior_filing.url}")
    out.append("")
    out.append("## Financial Snapshot")
    out.append("")
    out.extend(_financial_table(bundle.current_financials, bundle.prior_financials))
    out.append("")

    if bundle.llm_summary:
        out.append("## Evidence-Constrained AI Synthesis")
        out.append("")
        out.append(bundle.llm_summary.get("executive_summary", ""))
        out.append("")
        for item in bundle.llm_summary.get("priority_leads", []):
            out.append(f"- **{item.get('theme', 'Lead')}** — {item.get('why_it_matters', '')}")
            if item.get("follow_up_question"):
                out.append(f"  - Question: {item['follow_up_question']}")
            if item.get("evidence_ids"):
                out.append(f"  - Evidence: {', '.join(item['evidence_ids'])}")
        out.append("")

    out.append("## Research Leads")
    out.append("")
    if not bundle.leads:
        out.append("No changes cleared the current materiality thresholds.")
    for i, lead in enumerate(bundle.leads, 1):
        out.append(f"### {i}. {lead.title}")
        out.append("")
        out.append(f"- **Category:** {lead.category}")
        out.append(f"- **Signal score:** {lead.score}")
        out.append(f"- **Why it surfaced:** {lead.rationale}")
        if lead.analyst_question:
            out.append(f"- **Question to investigate:** {lead.analyst_question}")
        if lead.metrics:
            out.append(f"- **Comparison data:** `{json.dumps(lead.metrics, default=str)}`")
        if lead.evidence:
            out.append("- **Evidence:**")
            for ev in lead.evidence:
                out.append(
                    f"  - `{ev.evidence_id}` — {ev.period} / {ev.label}: {ev.excerpt}"
                )
        out.append("")
    return "\n".join(out)


def json_report(bundle: ResearchBundle) -> str:
    return json.dumps(asdict(bundle), indent=2, default=str)
