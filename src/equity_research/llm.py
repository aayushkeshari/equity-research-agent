from __future__ import annotations

import json
from typing import Any

from .models import ResearchLead


def _payload(leads: list[ResearchLead], max_leads: int = 12) -> list[dict[str, Any]]:
    rows = []
    for lead in leads[:max_leads]:
        rows.append(
            {
                "theme": lead.theme,
                "category": lead.category,
                "title": lead.title,
                "score": lead.score,
                "rationale": lead.rationale,
                "metrics": lead.metrics,
                "analyst_question": lead.analyst_question,
                "evidence": [
                    {
                        "id": e.evidence_id,
                        "period": e.period,
                        "label": e.label,
                        "excerpt": e.excerpt,
                    }
                    for e in lead.evidence
                ],
            }
        )
    return rows


def synthesize_with_openai(
    company_name: str,
    ticker: str,
    leads: list[ResearchLead],
    api_key: str,
    model: str,
) -> dict[str, Any]:
    """Optional layer. Deterministic evidence exists before this function runs."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the openai package to use --llm") from exc

    client = OpenAI(api_key=api_key)
    evidence = _payload(leads)
    instructions = f"""
You are assisting an equity-research analyst studying {company_name} ({ticker}).
You receive deterministic research leads from SEC filing text and XBRL facts.

Rules:
1. Use ONLY the supplied evidence and metrics.
2. Do not create financial facts, causes, management intentions, forecasts, or conclusions.
3. Treat each item as a research lead, not an investment recommendation.
4. Every observation must list supporting evidence IDs when evidence IDs exist.
5. Prefer changes that appear decision-relevant, surprising, or worth follow-up.
6. If the evidence does not establish causality, phrase the result as a question to investigate.

Return valid JSON only with this schema:
{{
  "executive_summary": "2-4 sentence evidence-constrained summary",
  "priority_leads": [
    {{
      "theme": "...",
      "why_it_matters": "...",
      "follow_up_question": "...",
      "evidence_ids": ["..."]
    }}
  ]
}}
""".strip()

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": json.dumps(evidence)},
        ],
    )
    text = response.output_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"executive_summary": text, "priority_leads": []}
