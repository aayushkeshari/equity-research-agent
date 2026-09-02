# Design Notes

## Core research question

For two comparable reporting periods:

> **What changed enough that an analyst should inspect it?**

The system intentionally does not decide whether a security is a buy or sell.

## Evidence contract

Text leads carry filing excerpts and accession numbers. Financial leads carry the exact XBRL concept, unit, period, value, and accession when available.

An optional LLM receives only this prebuilt evidence bundle. The LLM can prioritize and phrase questions, but it is not allowed to invent facts or causality.

## Period matching

SEC Company Facts may contain multiple facts for the same concept and end date, including quarterly and year-to-date durations. The normalizer scores candidate facts using:
- accession-number match,
- report-date match,
- filing form,
- fiscal period,
- filing date,
- duration fit (roughly 91 days for 10-Q and 365 for 10-K).

This is intentionally explicit and testable rather than hidden in a model prompt.

## Materiality heuristics

Initial thresholds are simple and explainable:
- raw financial facts: typically 8-10% change,
- derived margin/intensity ratios: at least 1 percentage point,
- text themes: weighted mention-count change.

These thresholds are research-routing heuristics, not statistical or investment materiality determinations.

## Next research-grade extensions

1. Add fiscal-period reconciliation for unusual 52/53-week calendars.
2. Build concept-specific fallback mappings for industry-specific taxonomies.
3. Add sentence embeddings to detect semantic changes beyond keyword counts.
4. Add earnings call transcripts from a licensed source.
5. Build cross-company screens for themes such as AI capex intensity.
6. Create an analyst-labelled evaluation set and measure precision/recall of surfaced leads.
7. Persist research runs in SQLite with hashes for reproducibility.
