"""
signals — run the exogenous-signal capture suite and emit a publishable digest.

One command the VPS can cron: collect futures metrics, capture news/social, and
refresh the macro/correlation panel, then write a Markdown digest
(state/signals/report.md) suitable for publishing to a website.

Usage:
    uv run python -m local_system.cli.signals                # capture + report
    uv run python -m local_system.cli.signals --report-only  # just rebuild report
    uv run python -m local_system.cli.signals --symbols BTCUSDT SOLUSDT
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from local_system.signals import SIGNALS_DIR


def _capture(symbols: list[str]) -> dict:
    from local_system.signals.futures import collect_futures
    from local_system.signals.macro import build_panel
    from local_system.signals.news.capture import run_capture

    out = {}
    print("Collecting futures metrics...", flush=True)
    fut = collect_futures(symbols)
    out["futures"] = {s: (0 if df.empty else len(df)) for s, df in fut.items()}

    print("Capturing news/social...", flush=True)
    news = run_capture()
    out["news"] = news

    print("Refreshing macro panel...", flush=True)
    panel = build_panel(lookback_days=365)
    out["macro_days"] = 0 if panel.empty else len(panel)
    return out


def _latest_futures_line(symbol: str) -> str:
    path = SIGNALS_DIR / f"futures_{symbol}.parquet"
    if not path.exists():
        return f"- **{symbol}**: no data"
    import pandas as pd

    df = pd.read_parquet(path)
    if df.empty:
        return f"- **{symbol}**: no data"
    last = df.iloc[-1]
    fund = last.get("funding_rate", float("nan"))
    oi = last.get("open_interest_usd", float("nan"))
    lsr = last.get("ls_account_ratio", float("nan"))
    top = last.get("top_ls_position_ratio", float("nan"))
    return (
        f"- **{symbol}**  funding `{fund * 100:+.4f}%`  |  "
        f"OI `${oi / 1e9:.2f}B`  |  retail L/S `{lsr:.2f}`  |  top-trader L/S `{top:.2f}`"
    )


def _recent_news(limit: int = 12, only_tags: set[str] | None = None) -> list[dict]:
    log = SIGNALS_DIR / "news.jsonl"
    if not log.exists():
        return []
    rows = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
    if only_tags:
        rows = [r for r in rows if set(r.get("tags", [])) & only_tags]
    return rows[:limit]


def _build_report(symbols: list[str]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Signal digest",
        "",
        f"_Generated {now}_",
        "",
        "## Futures positioning",
        "",
    ]
    lines += [_latest_futures_line(s) for s in symbols]

    # Correlations
    lines += ["", "## Cross-asset correlations", "", "```"]
    try:
        from local_system.signals.correlations import correlation_report
        from local_system.signals.macro import build_panel

        lines.append(correlation_report(build_panel(lookback_days=365), base="BTC"))
    except Exception as exc:  # noqa: BLE001
        lines.append(f"(unavailable: {exc})")
    lines.append("```")

    # Trump posts
    lines += ["", "## Latest Trump posts", ""]
    trump = [r for r in _recent_news(limit=200) if r.get("source", "").startswith("trump")][:5]
    if trump:
        for r in trump:
            lines.append(f"- `{r['ts'][:16]}` {r['title'][:140]}")
    else:
        lines.append("- (none captured)")

    # High-impact headlines
    lines += ["", "## Market-moving headlines (fed / regulation / macro / hacks)", ""]
    hot = _recent_news(limit=10, only_tags={"fed", "regulation", "macro", "hack"})
    if hot:
        for r in hot:
            tags = ",".join(r.get("tags", []))
            lines.append(f"- `{r['ts'][:16]}` [{tags}] {r['title'][:140]}")
    else:
        lines.append("- (none captured)")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run signal capture + emit digest")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "SOLUSDT"])
    parser.add_argument(
        "--report-only", action="store_true", help="Skip capture, just rebuild report"
    )
    args = parser.parse_args()

    if not args.report_only:
        summary = _capture(args.symbols)
        print(f"\nCapture summary: {json.dumps(summary)}")

    report = _build_report(args.symbols)
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    (SIGNALS_DIR / "report.md").write_text(report, encoding="utf-8")
    print(f"\nReport written to {SIGNALS_DIR / 'report.md'}\n")
    print(report)


if __name__ == "__main__":
    main()
