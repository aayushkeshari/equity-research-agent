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


def test_mismatched_ytd_durations_are_not_compared():
    cf = {"facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            fact(120, "2026-03-29", "2026-06-27", "CUR", fp="Q3"),
            fact(110, "2025-03-30", "2025-06-28", "OLD", fp="Q2"),
        ]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            # Current filing exposes a nine-month cumulative cash-flow fact.
            fact(6.8, "2025-09-28", "2026-06-27", "CUR", fp="Q3"),
            # Prior filing exposes a six-month cumulative cash-flow fact.
            fact(4.34, "2025-09-28", "2026-03-28", "OLD", fp="Q2"),
        ]}},
    }}}
    cur = build_financial_period(cf, filing("2026-06-27", "CUR", fp="Q3"))
    old = build_financial_period(cf, filing("2026-03-28", "OLD", fp="Q2"))

    assert "capex_intensity" not in cur.derived
    leads = compare_financial_periods(cur, old)
    assert not any(x.theme == "capex" for x in leads)
    assert not any(x.theme == "capex_intensity" for x in leads)


def test_similar_quarter_durations_are_comparable():
    cf = {"facts": {"us-gaap": {
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            fact(12, "2026-03-29", "2026-06-27", "CUR", fp="Q3"),
            fact(10, "2025-03-30", "2025-06-28", "OLD", fp="Q2"),
        ]}},
    }}}
    cur = build_financial_period(cf, filing("2026-06-27", "CUR", fp="Q3"))
    old = build_financial_period(cf, filing("2025-06-28", "OLD", fp="Q2"))
    leads = compare_financial_periods(cur, old)
    assert any(x.theme == "capex" for x in leads)


def test_free_cash_flow_not_compared_across_mismatched_ytd_durations():
    cf = {"facts": {"us-gaap": {
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
            fact(116.996, "2025-09-28", "2026-06-27", "CUR", fp="Q3"),
            fact(82.627, "2025-09-28", "2026-03-28", "OLD", fp="Q2"),
        ]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            fact(6.799, "2025-09-28", "2026-06-27", "CUR", fp="Q3"),
            fact(4.344, "2025-09-28", "2026-03-28", "OLD", fp="Q2"),
        ]}},
    }}}
    cur = build_financial_period(cf, filing("2026-06-27", "CUR", fp="Q3"))
    old = build_financial_period(cf, filing("2026-03-28", "OLD", fp="Q2"))

    # FCF is valid within each filing because OCF and capex share the same span.
    assert "free_cash_flow" in cur.derived
    assert "free_cash_flow" in old.derived

    # But the current 272-day FCF must not be compared with the prior 181-day FCF.
    leads = compare_financial_periods(cur, old)
    assert not any(x.theme == "free_cash_flow" for x in leads)
