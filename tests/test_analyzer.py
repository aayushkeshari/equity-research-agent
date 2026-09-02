from equity_research.analyzer import compare_filings
from equity_research.models import Filing, FilingMetadata


def meta(date: str):
    return FilingMetadata(
        ticker="TEST", company_name="Test Corp", cik="0000000001", form="10-Q",
        accession_number=f"0000000001-26-{date[-2:]}", filing_date=date, report_date=date,
        fiscal_year="2026", fiscal_period="Q2", primary_document="test.htm",
        url="https://example.com/test.htm",
    )


def test_detects_ai_infrastructure_change():
    old_text = "We operate data center infrastructure."
    new_text = (
        "We expanded data center capacity. Artificial intelligence demand increased GPU requirements. "
        "We invested in compute capacity and additional data center infrastructure."
    )
    old = Filing(meta("2026-03-31"), old_text, {"mda": old_text})
    new = Filing(meta("2026-06-30"), new_text, {"mda": new_text})
    leads = compare_filings(new, old)
    assert any(x.theme == "ai_infrastructure" for x in leads)
