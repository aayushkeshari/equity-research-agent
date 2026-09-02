from equity_research.financials import build_financial_period, compare_financial_periods
from equity_research.models import FilingMetadata


def filing(report_date: str, accession: str, fp: str = "Q2"):
    return FilingMetadata(
        ticker="TEST", company_name="Test Corp", cik="0000000001", form="10-Q",
        accession_number=accession, filing_date=report_date, report_date=report_date,
        fiscal_year="2026", fiscal_period=fp, primary_document="test.htm",
        url="https://example.com",
    )


def fact(val, start, end, accn, concept_form="10-Q", fp="Q2"):
    return {"start": start, "end": end, "val": val, "accn": accn, "fy": 2026, "fp": fp, "form": concept_form, "filed": end}


def test_xbrl_normalization_and_derived_metrics():
    cf = {"facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            fact(120, "2026-04-01", "2026-06-30", "A"),
            fact(100, "2025-04-01", "2025-06-30", "B"),
        ]}},
        "GrossProfit": {"units": {"USD": [
            fact(72, "2026-04-01", "2026-06-30", "A"),
            fact(55, "2025-04-01", "2025-06-30", "B"),
        ]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            fact(24, "2026-04-01", "2026-06-30", "A"),
            fact(10, "2025-04-01", "2025-06-30", "B"),
        ]}},
    }}}
    cur = build_financial_period(cf, filing("2026-06-30", "A"))
    old = build_financial_period(cf, filing("2025-06-30", "B"))
    assert cur.facts["revenue"].value == 120
    assert abs(cur.derived["gross_margin"] - 0.60) < 1e-9
    assert abs(cur.derived["capex_intensity"] - 0.20) < 1e-9
    leads = compare_financial_periods(cur, old)
    assert any(x.theme == "capex" for x in leads)
    assert any(x.theme == "capex_intensity" for x in leads)
