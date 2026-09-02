from equity_research.parser import extract_sections, html_to_text


def test_html_to_text_removes_scripts():
    html = "<html><body><h1>Hello</h1><script>bad()</script><p>World</p></body></html>"
    text = html_to_text(html)
    assert "Hello" in text and "World" in text and "bad()" not in text


def test_extract_sections_finds_risk_factors():
    text = """
ITEM 1. BUSINESS
Business content.

ITEM 1A. RISK FACTORS
Our business faces cybersecurity risk and supply chain uncertainty. """ + ("More risk. " * 400) + """
ITEM 1B. UNRESOLVED STAFF COMMENTS
Nothing.
"""
    sections = extract_sections(text)
    assert "risk_factors" in sections
    assert "cybersecurity risk" in sections["risk_factors"]
