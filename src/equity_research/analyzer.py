from __future__ import annotations

import math
import re

from .models import Evidence, Filing, ResearchLead


THEMES: dict[str, tuple[str, ...]] = {
    "ai_infrastructure": (
        "artificial intelligence", "machine learning", "generative ai", "data center",
        "datacenter", "gpu", "accelerator", "inference", "training", "compute capacity",
        "large language model", "foundation model",
    ),
    "capital_investment": (
        "capital expenditure", "capital expenditures", "capital spending", "property and equipment",
        "infrastructure investment", "capacity expansion",
    ),
    "cloud_software": (
        "cloud", "subscription", "software", "platform", "saas", "monetization",
    ),
    "profitability": (
        "gross margin", "operating margin", "operating income", "profitability",
        "cost of revenue", "cost of sales",
    ),
    "competition": ("competition", "competitive", "market share", "pricing pressure"),
    "regulation": ("regulation", "regulatory", "antitrust", "export control", "privacy law"),
    "cybersecurity": ("cybersecurity", "cyber attack", "security incident", "data breach"),
    "supply_chain": ("supply chain", "supply constraint", "shortage", "supplier", "capacity constraint"),
}

ANALYST_QUESTIONS = {
    "ai_infrastructure": "Is the change signaling new demand, a capacity bottleneck, higher infrastructure intensity, or a shift in product strategy?",
    "capital_investment": "What return is management expecting from the incremental capital, and when should it translate into revenue or efficiency?",
    "cloud_software": "Does the language change indicate stronger monetization, changing customer demand, or a shift in go-to-market economics?",
    "profitability": "What mix, pricing, utilization, or cost changes are driving the change in profitability language?",
    "competition": "Is competitive intensity changing enough to affect pricing, share, product cadence, or customer acquisition?",
    "regulation": "Could the new regulatory discussion change addressable markets, costs, product design, or timing?",
    "cybersecurity": "Is the company describing a new incident, an elevated risk, or simply expanded boilerplate disclosure?",
    "supply_chain": "Is supply becoming a growth constraint, a margin issue, or a source of working-capital risk?",
}


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    return re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", compact)


def _term_count(text: str, terms: tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(lower.count(term) for term in terms)


def _best_excerpts(text: str, terms: tuple[str, ...], limit: int = 2, max_chars: int = 800) -> list[str]:
    scored = []
    for sentence in _sentences(text):
        low = sentence.lower()
        hits = sum(1 for t in terms if t in low)
        if hits:
            scored.append((hits * 10 + min(len(sentence), 500) / 500, sentence.strip()))
    scored.sort(reverse=True, key=lambda x: x[0])

    output, seen = [], set()
    for _, sentence in scored:
        key = sentence[:180].lower()
        if key in seen:
            continue
        seen.add(key)
        if len(sentence) > max_chars:
            sentence = sentence[: max_chars - 1].rstrip() + "…"
        output.append(sentence)
        if len(output) >= limit:
            break
    return output


def compare_filings(new: Filing, old: Filing) -> list[ResearchLead]:
    leads: list[ResearchLead] = []
    section_priority = ("mda", "risk_factors", "business", "full_filing")

    for theme, terms in THEMES.items():
        best_for_theme: ResearchLead | None = None
        for section in section_priority:
            new_text = new.sections.get(section, "")
            old_text = old.sections.get(section, "")
            if not new_text or not old_text:
                continue

            new_count = _term_count(new_text, terms)
            old_count = _term_count(old_text, terms)
            if new_count == 0 and old_count == 0:
                continue

            delta = new_count - old_count
            relative = (new_count + 1) / (old_count + 1)
            score = abs(delta) + 2.0 * abs(math.log(relative))
            if score < 2.5:
                continue

            evidence: list[Evidence] = []
            for idx, excerpt in enumerate(_best_excerpts(new_text, terms, limit=2), 1):
                evidence.append(
                    Evidence(
                        evidence_id=f"TEXT-NEW-{theme}-{idx}",
                        source_type="filing_text",
                        period=new.metadata.report_date or new.metadata.filing_date,
                        label=section,
                        excerpt=excerpt,
                        accession_number=new.metadata.accession_number,
                        source_url=new.metadata.url,
                    )
                )
            for idx, excerpt in enumerate(_best_excerpts(old_text, terms, limit=1), 1):
                evidence.append(
                    Evidence(
                        evidence_id=f"TEXT-OLD-{theme}-{idx}",
                        source_type="filing_text",
                        period=old.metadata.report_date or old.metadata.filing_date,
                        label=section,
                        excerpt=excerpt,
                        accession_number=old.metadata.accession_number,
                        source_url=old.metadata.url,
                    )
                )

            direction = "increased" if delta > 0 else "decreased"
            lead = ResearchLead(
                theme=theme,
                title=f"{theme.replace('_', ' ').title()} discussion {direction}",
                score=round(score, 2),
                rationale=(
                    f"Theme mentions in {section} changed from {old_count} to {new_count}. "
                    "This is a retrieval signal for analyst review, not an investment conclusion."
                ),
                evidence=evidence,
                metrics={
                    "new_hits": new_count,
                    "old_hits": old_count,
                    "delta": delta,
                    "relative_ratio": round(relative, 2),
                    "section": section,
                },
                analyst_question=ANALYST_QUESTIONS.get(theme),
                category="text",
            )
            if best_for_theme is None or lead.score > best_for_theme.score:
                best_for_theme = lead

        if best_for_theme:
            leads.append(best_for_theme)

    return sorted(leads, key=lambda x: x.score, reverse=True)
