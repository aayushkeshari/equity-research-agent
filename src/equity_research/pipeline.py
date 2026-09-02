from __future__ import annotations

from .analyzer import compare_filings
from .financials import build_financial_period, compare_financial_periods
from .llm import synthesize_with_openai
from .models import ResearchBundle
from .parser import parse_filing
from .sec_client import SECClient


def run_research(
    client: SECClient,
    ticker: str,
    form: str = "10-Q",
    use_llm: bool = False,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-5-mini",
    max_leads: int = 16,
) -> ResearchBundle:
    filings = client.recent_filings(ticker, form=form, limit=8)
    if len(filings) < 2:
        raise ValueError(f"Need at least two {form} filings; found {len(filings)}")

    current_meta, prior_meta = filings[0], filings[1]
    current = parse_filing(current_meta, client.download_filing(current_meta))
    prior = parse_filing(prior_meta, client.download_filing(prior_meta))

    company_facts = client.company_facts(ticker)
    current_fin = build_financial_period(company_facts, current_meta)
    prior_fin = build_financial_period(company_facts, prior_meta)

    leads = compare_financial_periods(current_fin, prior_fin) + compare_filings(current, prior)
    leads = sorted(leads, key=lambda x: x.score, reverse=True)[:max_leads]

    llm_summary = None
    if use_llm:
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when --llm is enabled")
        llm_summary = synthesize_with_openai(
            current_meta.company_name,
            ticker.upper(),
            leads,
            api_key=openai_api_key,
            model=openai_model,
        )

    return ResearchBundle(
        ticker=ticker.upper(),
        company_name=current_meta.company_name,
        form=form,
        current_filing=current_meta,
        prior_filing=prior_meta,
        current_financials=current_fin,
        prior_financials=prior_fin,
        leads=leads,
        llm_summary=llm_summary,
    )
