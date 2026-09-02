from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .models import Filing, FilingMetadata


SECTION_PATTERNS = {
    "risk_factors": [
        r"\bitem\s+1a\.?\s+risk\s+factors\b",
    ],
    "mda": [
        r"\bitem\s+7\.?\s+management['’]s\s+discussion",
        r"\bitem\s+2\.?\s+management['’]s\s+discussion",
    ],
    "business": [r"\bitem\s+1\.?\s+business\b"],
    "financial_statements": [
        r"\bitem\s+8\.?\s+financial\s+statements",
        r"\bitem\s+1\.?\s+financial\s+statements",
    ],
}


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _all_pattern_positions(text: str, patterns: list[str]) -> list[int]:
    positions: list[int] = []
    for pattern in patterns:
        positions.extend(m.start() for m in re.finditer(pattern, text, flags=re.I))
    return sorted(set(positions))


def extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {"full_filing": text}
    heading_re = re.compile(
        r"(?im)^\s*item\s+(?:1a|1b|1c|1|2|3|4|5|6|7a|7|8|9a|9b|9c|9|10|11|12|13|14|15|16)\.?(?:\s|$)"
    )
    headings = [m.start() for m in heading_re.finditer(text)]

    for name, patterns in SECTION_PATTERNS.items():
        positions = _all_pattern_positions(text, patterns)
        if not positions:
            continue

        # Filings often contain a table-of-contents occurrence first. Prefer the
        # first occurrence that yields a substantial section.
        best = None
        for start in positions:
            next_heads = [p for p in headings if p > start + 50]
            end = min(next_heads) if next_heads else min(len(text), start + 150_000)
            chunk = text[start:end].strip()
            if best is None or len(chunk) > len(best):
                best = chunk
            if len(chunk) >= 2_000:
                best = chunk
                break
        if best:
            sections[name] = best

    return sections


def parse_filing(metadata: FilingMetadata, html: str) -> Filing:
    text = html_to_text(html)
    return Filing(metadata=metadata, text=text, sections=extract_sections(text))
