from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .models import FilingMetadata


class SECClient:
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    def __init__(
        self,
        user_agent: str,
        cache_dir: str | Path = ".cache/sec",
        min_interval_seconds: float = 0.20,
    ):
        if not user_agent.strip():
            raise ValueError("A descriptive SEC User-Agent is required")
        self.user_agent = user_agent.strip()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json,text/html,*/*",
            }
        )

    def _get(self, url: str, cache_key: str, force: bool = False) -> bytes:
        path = self.cache_dir / cache_key
        if path.exists() and not force:
            return path.read_bytes()

        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

        response = self.session.get(url, timeout=45)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return response.content

    def _json(self, url: str, cache_key: str, force: bool = False) -> dict[str, Any]:
        return json.loads(self._get(url, cache_key, force=force))

    def ticker_record(self, ticker: str) -> dict[str, Any]:
        data = self._json(self.TICKERS_URL, "company_tickers.json")
        target = ticker.upper()
        for row in data.values():
            if row["ticker"].upper() == target:
                return row
        raise ValueError(f"Ticker not found in SEC ticker map: {ticker}")

    def ticker_to_cik(self, ticker: str) -> str:
        return str(self.ticker_record(ticker)["cik_str"]).zfill(10)

    def submissions(self, ticker: str) -> dict[str, Any]:
        cik = self.ticker_to_cik(ticker)
        return self._json(
            self.SUBMISSIONS_URL.format(cik=cik),
            f"submissions/{cik}.json",
        )

    def recent_filings(
        self,
        ticker: str,
        form: str = "10-Q",
        limit: int = 8,
    ) -> list[FilingMetadata]:
        cik = self.ticker_to_cik(ticker)
        data = self.submissions(ticker)
        recent = data["filings"]["recent"]
        company_name = data.get("name") or self.ticker_record(ticker).get("title", ticker)

        rows: list[FilingMetadata] = []
        for i, filing_form in enumerate(recent["form"]):
            if filing_form != form:
                continue

            accession = recent["accessionNumber"][i]
            primary_document = recent["primaryDocument"][i]
            accession_no_dashes = accession.replace("-", "")
            cik_no_zeros = str(int(cik))
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik_no_zeros}/{accession_no_dashes}/{primary_document}"
            )

            def col(name: str, default=None):
                values = recent.get(name, [])
                return values[i] if i < len(values) else default

            rows.append(
                FilingMetadata(
                    ticker=ticker.upper(),
                    company_name=company_name,
                    cik=cik,
                    form=filing_form,
                    accession_number=accession,
                    filing_date=col("filingDate", ""),
                    report_date=col("reportDate", ""),
                    fiscal_year=str(col("fiscalYear", "")) or None,
                    fiscal_period=col("fiscalPeriod", None),
                    primary_document=primary_document,
                    url=filing_url,
                )
            )
            if len(rows) >= limit:
                break
        return rows

    def download_filing(self, metadata: FilingMetadata) -> str:
        key = (
            f"filings/{metadata.cik}/"
            f"{metadata.accession_number.replace('-', '')}/"
            f"{metadata.primary_document}"
        )
        return self._get(metadata.url, key).decode("utf-8", errors="replace")

    def company_facts(self, ticker: str, force: bool = False) -> dict[str, Any]:
        cik = self.ticker_to_cik(ticker)
        return self._json(
            self.COMPANY_FACTS_URL.format(cik=cik),
            f"companyfacts/{cik}.json",
            force=force,
        )
