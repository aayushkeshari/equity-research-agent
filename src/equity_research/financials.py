from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .models import Evidence, FinancialFact, FinancialPeriod, FilingMetadata, ResearchLead


@dataclass(frozen=True)
class MetricSpec:
    label: str
    concepts: tuple[str, ...]
    preferred_units: tuple[str, ...] = ("USD",)
    duration: bool = True


METRICS: dict[str, MetricSpec] = {
    "revenue": MetricSpec(
        "Revenue",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
    ),
    "gross_profit": MetricSpec("Gross Profit", ("GrossProfit",)),
    "operating_income": MetricSpec(
        "Operating Income",
        ("OperatingIncomeLoss",),
    ),
    "net_income": MetricSpec(
        "Net Income",
        ("NetIncomeLoss", "ProfitLoss"),
    ),
    "research_and_development": MetricSpec(
        "R&D",
        ("ResearchAndDevelopmentExpense",),
    ),
    "capex": MetricSpec(
        "Capital Expenditures",
        (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForAdditionsToPropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ),
    ),
    "operating_cash_flow": MetricSpec(
        "Operating Cash Flow",
        ("NetCashProvidedByUsedInOperatingActivities",),
    ),
    "cash": MetricSpec(
        "Cash & Cash Equivalents",
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        duration=False,
    ),
    "assets": MetricSpec("Total Assets", ("Assets",), duration=False),
    "liabilities": MetricSpec("Total Liabilities", ("Liabilities",), duration=False),
}


def _days_between(start: str | None, end: str) -> int | None:
    if not start:
        return None
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _fact_duration_days(fact: FinancialFact) -> int | None:
    return _days_between(fact.start, fact.end)


def _duration_compatible(a: FinancialFact, b: FinancialFact, tolerance_days: int = 7) -> bool:
    """Return True when two duration facts represent comparable spans.

    Instant facts (no start date) are comparable by period end. Duration facts must
    have nearly equal spans so a quarter is not compared with a cumulative YTD fact.
    """
    a_days = _fact_duration_days(a)
    b_days = _fact_duration_days(b)
    if a_days is None or b_days is None:
        return a_days is None and b_days is None
    return abs(a_days - b_days) <= tolerance_days


def _candidate_score(
    fact: dict[str, Any],
    filing: FilingMetadata,
    duration: bool,
) -> tuple[int, int, int, int, int]:
    """Higher tuple is better."""
    accn_match = int(fact.get("accn") == filing.accession_number)
    form_match = int(fact.get("form") == filing.form)
    end_match = int(fact.get("end") == filing.report_date)
    fp_match = int(bool(filing.fiscal_period) and fact.get("fp") == filing.fiscal_period)
    filed_match = int(fact.get("filed") == filing.filing_date)

    if duration:
        days = _days_between(fact.get("start"), fact.get("end", filing.report_date))
        # For 10-Q prefer quarter facts over year-to-date when both are present.
        duration_fit = 0
        if filing.form == "10-Q" and days is not None:
            duration_fit = max(0, 120 - abs(days - 91))
        elif filing.form == "10-K" and days is not None:
            duration_fit = max(0, 420 - abs(days - 365))
    else:
        duration_fit = 100 if fact.get("end") == filing.report_date else 0

    return (accn_match, end_match, form_match, fp_match, filed_match + duration_fit)


def _find_metric_fact(
    company_facts: dict[str, Any],
    metric: str,
    filing: FilingMetadata,
) -> FinancialFact | None:
    spec = METRICS[metric]
    gaap = company_facts.get("facts", {}).get("us-gaap", {})

    best: tuple[tuple[int, int, int, int, int], FinancialFact] | None = None
    for concept in spec.concepts:
        node = gaap.get(concept)
        if not node:
            continue
        units = node.get("units", {})

        unit_names = list(spec.preferred_units) + [u for u in units if u not in spec.preferred_units]
        for unit in unit_names:
            for raw in units.get(unit, []):
                if raw.get("form") != filing.form:
                    continue
                if raw.get("end") != filing.report_date and raw.get("accn") != filing.accession_number:
                    continue
                if "val" not in raw:
                    continue
                try:
                    value = float(raw["val"])
                except (TypeError, ValueError):
                    continue

                ff = FinancialFact(
                    metric=metric,
                    label=spec.label,
                    concept=concept,
                    unit=unit,
                    value=value,
                    start=raw.get("start"),
                    end=raw.get("end", ""),
                    filed=raw.get("filed", ""),
                    form=raw.get("form", ""),
                    accession_number=raw.get("accn"),
                    fiscal_year=raw.get("fy"),
                    fiscal_period=raw.get("fp"),
                    frame=raw.get("frame"),
                )
                score = _candidate_score(raw, filing, spec.duration)
                if best is None or score > best[0]:
                    best = (score, ff)

    return best[1] if best else None


def _derived(facts: dict[str, FinancialFact]) -> dict[str, float]:
    out: dict[str, float] = {}

    def v(name: str) -> float | None:
        fact = facts.get(name)
        return fact.value if fact else None

    def compatible(a: str, b: str) -> bool:
        fa, fb = facts.get(a), facts.get(b)
        return bool(fa and fb and _duration_compatible(fa, fb))

    revenue = v("revenue")
    gross = v("gross_profit")
    op = v("operating_income")
    net = v("net_income")
    rnd = v("research_and_development")
    capex = v("capex")
    ocf = v("operating_cash_flow")

    if revenue and revenue != 0:
        if gross is not None and compatible("revenue", "gross_profit"):
            out["gross_margin"] = gross / revenue
        if op is not None and compatible("revenue", "operating_income"):
            out["operating_margin"] = op / revenue
        if net is not None and compatible("revenue", "net_income"):
            out["net_margin"] = net / revenue
        if rnd is not None and compatible("revenue", "research_and_development"):
            out["rnd_intensity"] = rnd / revenue
        if capex is not None and compatible("revenue", "capex"):
            out["capex_intensity"] = capex / revenue
    if ocf is not None and capex is not None and compatible("operating_cash_flow", "capex"):
        out["free_cash_flow"] = ocf - capex

    return out


def build_financial_period(
    company_facts: dict[str, Any],
    filing: FilingMetadata,
) -> FinancialPeriod:
    facts: dict[str, FinancialFact] = {}
    for metric in METRICS:
        fact = _find_metric_fact(company_facts, metric, filing)
        if fact:
            facts[metric] = fact
    return FinancialPeriod(
        label=f"{filing.form} {filing.report_date}",
        end_date=filing.report_date,
        facts=facts,
        derived=_derived(facts),
    )


def _pct_change(new: float, old: float) -> float | None:
    if old == 0:
        return None
    return (new - old) / abs(old)


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


def _fact_evidence(fact: FinancialFact, period: str, idx: int) -> Evidence:
    return Evidence(
        evidence_id=f"XBRL-{fact.metric}-{idx}",
        source_type="xbrl",
        period=period,
        label=f"us-gaap:{fact.concept}",
        excerpt=(
            f"{fact.label}: {_money(fact.value)} ({fact.unit})"
            + (f" | {fact.start} to {fact.end} ({_fact_duration_days(fact)} days)" if fact.start else f" | as of {fact.end}")
        ),
        accession_number=fact.accession_number,
        metadata={
            "metric": fact.metric,
            "concept": fact.concept,
            "value": fact.value,
            "unit": fact.unit,
            "start": fact.start,
            "end": fact.end,
            "frame": fact.frame,
            "duration_days": _fact_duration_days(fact),
        },
    )


ANALYST_QUESTIONS = {
    "revenue": "What is driving the change in growth, and is the mix sustainable?",
    "gross_profit": "Is gross-profit growth keeping pace with revenue, and what does that imply about mix or unit economics?",
    "operating_income": "Are operating leverage and cost discipline improving or deteriorating?",
    "net_income": "How much of the earnings change is operational versus tax, interest, or other non-operating items?",
    "research_and_development": "Is R&D investment scaling ahead of revenue, and what products or technical capabilities are absorbing the spend?",
    "capex": "Is incremental infrastructure investment leading demand, responding to capacity constraints, or changing the return profile of growth?",
    "operating_cash_flow": "What explains the cash-conversion change relative to reported earnings?",
    "cash": "What is driving the balance-sheet liquidity change, and how might management deploy the capital?",
    "assets": "Which asset categories are driving balance-sheet expansion or contraction?",
    "liabilities": "Is liability growth operational, financing-related, or a sign of working-capital change?",
    "gross_margin": "What mix, pricing, utilization, or input-cost changes explain the margin movement?",
    "operating_margin": "Is the change structural operating leverage or a temporary spending/mix effect?",
    "net_margin": "Which operating and non-operating factors explain the margin movement?",
    "rnd_intensity": "Is technical investment becoming more or less intensive relative to the revenue base?",
    "capex_intensity": "Is the business becoming more capital intensive, and what return should that incremental investment earn?",
    "free_cash_flow": "What is driving the change in cash generation after capital investment?",
}


def compare_financial_periods(
    current: FinancialPeriod,
    prior: FinancialPeriod,
) -> list[ResearchLead]:
    leads: list[ResearchLead] = []

    # Raw facts. Materiality thresholds differ by metric class.
    for metric, current_fact in current.facts.items():
        prior_fact = prior.facts.get(metric)
        if not prior_fact:
            continue

        # Never compare a standalone quarter with a cumulative YTD duration.
        # This is especially important for cash-flow concepts that companies may
        # disclose only cumulatively in 10-Q XBRL facts.
        if current_fact.start or prior_fact.start:
            if not _duration_compatible(current_fact, prior_fact):
                continue

        pct = _pct_change(current_fact.value, prior_fact.value)
        if pct is None:
            continue

        abs_pct = abs(pct)
        threshold = 0.10
        if metric in {"revenue", "gross_profit", "operating_income", "net_income"}:
            threshold = 0.08
        if abs_pct < threshold:
            continue

        direction = "increased" if pct > 0 else "decreased"
        score = min(25.0, 5.0 + abs_pct * 20.0)
        evidence = [
            _fact_evidence(current_fact, current.end_date, 1),
            _fact_evidence(prior_fact, prior.end_date, 2),
        ]
        leads.append(
            ResearchLead(
                theme=metric,
                title=f"{current_fact.label} {direction} {abs_pct:.1%}",
                score=round(score, 2),
                rationale=(
                    f"{current_fact.label} moved from {_money(prior_fact.value)} "
                    f"to {_money(current_fact.value)}, a {pct:+.1%} change between "
                    f"the comparable filing periods."
                ),
                evidence=evidence,
                metrics={
                    "current": current_fact.value,
                    "prior": prior_fact.value,
                    "pct_change": pct,
                    "unit": current_fact.unit,
                },
                analyst_question=ANALYST_QUESTIONS.get(metric),
                category="financial",
            )
        )

    # Derived ratios. Use percentage-point thresholds rather than % change.
    for metric, current_value in current.derived.items():
        if metric not in prior.derived:
            continue

        # Derived metrics can be valid within each individual filing but still be
        # invalid to compare across filings when their source facts span different
        # durations. For example, FCF computed from 9-month OCF/capex must not be
        # compared with FCF computed from 6-month OCF/capex.
        if metric == "free_cash_flow":
            source_metrics = ("operating_cash_flow", "capex")
            if any(
                source not in current.facts
                or source not in prior.facts
                or not _duration_compatible(current.facts[source], prior.facts[source])
                for source in source_metrics
            ):
                continue

        prior_value = prior.derived[metric]
        delta = current_value - prior_value

        if metric == "free_cash_flow":
            pct = _pct_change(current_value, prior_value)
            if pct is None or abs(pct) < 0.10:
                continue
            score = min(25.0, 5.0 + abs(pct) * 20.0)
            rationale = (
                f"Free cash flow moved from {_money(prior_value)} to "
                f"{_money(current_value)} ({pct:+.1%})."
            )
            title = f"Free cash flow {'increased' if pct > 0 else 'decreased'} {abs(pct):.1%}"
            metrics = {"current": current_value, "prior": prior_value, "pct_change": pct}
        else:
            if abs(delta) < 0.01:  # one percentage point
                continue
            score = min(25.0, 6.0 + abs(delta) * 250.0)
            pretty = metric.replace("_", " ").title()
            title = f"{pretty} {'increased' if delta > 0 else 'decreased'} {abs(delta):.1%} pts"
            rationale = (
                f"{pretty} moved from {prior_value:.1%} to {current_value:.1%}, "
                f"a {delta:+.1%} percentage-point change."
            )
            metrics = {"current": current_value, "prior": prior_value, "delta_points": delta}

        leads.append(
            ResearchLead(
                theme=metric,
                title=title,
                score=round(score, 2),
                rationale=rationale,
                evidence=[],
                metrics=metrics,
                analyst_question=ANALYST_QUESTIONS.get(metric),
                category="financial",
            )
        )

    return sorted(leads, key=lambda x: x.score, reverse=True)
