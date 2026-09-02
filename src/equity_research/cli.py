from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from .config import Settings
from .financials import build_financial_period
from .pipeline import run_research
from .report import json_report, markdown_report
from .sec_client import SECClient

console = Console()


def _client(settings: Settings) -> SECClient:
    return SECClient(settings.sec_user_agent, cache_dir=settings.cache_dir)


def research_command(args: argparse.Namespace) -> None:
    load_dotenv()
    settings = Settings.from_env()
    console.print(f"[bold]Running research pipeline for {args.ticker.upper()}...[/bold]")
    bundle = run_research(
        _client(settings),
        ticker=args.ticker,
        form=args.form,
        use_llm=args.llm,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        max_leads=args.max_leads,
    )
    md = markdown_report(bundle)
    if args.markdown:
        p = Path(args.markdown); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(md, encoding="utf-8")
        console.print(f"[green]Markdown: {p}[/green]")
    else:
        console.print(md)
    if args.json:
        p = Path(args.json); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json_report(bundle), encoding="utf-8")
        console.print(f"[green]JSON: {p}[/green]")


def financials_command(args: argparse.Namespace) -> None:
    load_dotenv()
    settings = Settings.from_env()
    client = _client(settings)
    filings = client.recent_filings(args.ticker, form=args.form, limit=2)
    if len(filings) < 2:
        raise SystemExit("Need two comparable filings")
    cf = client.company_facts(args.ticker)
    for filing in filings[:2]:
        period = build_financial_period(cf, filing)
        console.print(f"\n[bold]{period.label}[/bold]")
        for fact in period.facts.values():
            console.print(f"{fact.label}: {fact.value:,.0f} {fact.unit} ({fact.concept})")
        for k, v in period.derived.items():
            console.print(f"{k}: {v:.4f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="equity-research")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("research", help="Run filing + XBRL research pipeline")
    r.add_argument("ticker")
    r.add_argument("--form", default="10-Q", choices=["10-Q", "10-K"])
    r.add_argument("--markdown")
    r.add_argument("--json")
    r.add_argument("--llm", action="store_true")
    r.add_argument("--max-leads", type=int, default=16)
    r.set_defaults(func=research_command)

    f = sub.add_parser("financials", help="Inspect normalized XBRL financials")
    f.add_argument("ticker")
    f.add_argument("--form", default="10-Q", choices=["10-Q", "10-K"])
    f.set_defaults(func=financials_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
