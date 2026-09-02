from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FilingMetadata:
    ticker: str
    company_name: str
    cik: str
    form: str
    accession_number: str
    filing_date: str
    report_date: str
    fiscal_year: str | None
    fiscal_period: str | None
    primary_document: str
    url: str


@dataclass
class Filing:
    metadata: FilingMetadata
    text: str
    sections: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_type: str
    period: str
    label: str
    excerpt: str
    accession_number: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchLead:
    theme: str
    title: str
    score: float
    rationale: str
    evidence: list[Evidence]
    metrics: dict[str, Any] = field(default_factory=dict)
    analyst_question: str | None = None
    category: str = "text"


@dataclass(frozen=True)
class FinancialFact:
    metric: str
    label: str
    concept: str
    unit: str
    value: float
    start: str | None
    end: str
    filed: str
    form: str
    accession_number: str | None
    fiscal_year: int | None
    fiscal_period: str | None
    frame: str | None


@dataclass
class FinancialPeriod:
    label: str
    end_date: str
    facts: dict[str, FinancialFact] = field(default_factory=dict)
    derived: dict[str, float] = field(default_factory=dict)


@dataclass
class ResearchBundle:
    ticker: str
    company_name: str
    form: str
    current_filing: FilingMetadata
    prior_filing: FilingMetadata
    current_financials: FinancialPeriod
    prior_financials: FinancialPeriod
    leads: list[ResearchLead]
    llm_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
