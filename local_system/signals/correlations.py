"""
correlations.py — cross-asset & macro correlation analysis.

Operates on the daily panel from macro.py. Correlations are computed on daily
**returns** (pct_change), never on price levels — correlating levels of two
trending series produces spuriously high numbers that say nothing about
co-movement. Pearson correlation of returns is the standard.

What it surfaces:
  - the trailing correlation matrix (e.g. last 30 / 90 days)
  - rolling correlation of a base asset (default BTC) vs every other series,
    so regime shifts are visible (e.g. BTC decoupling from the S&P, or coupling
    to the dollar)

Usage:
    from local_system.signals.macro import build_panel
    from local_system.signals.correlations import correlation_report
    print(correlation_report(build_panel()))
"""

from __future__ import annotations

import pandas as pd


def to_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns; drop the first NaN row."""
    return panel.pct_change().dropna(how="all")


def correlation_matrix(panel: pd.DataFrame, window: int | None = None) -> pd.DataFrame:
    """Pearson correlation matrix of daily returns (full sample or trailing window)."""
    rets = to_returns(panel)
    if window:
        rets = rets.tail(window)
    return rets.corr()


def rolling_corr_vs(panel: pd.DataFrame, base: str = "BTC", window: int = 30) -> pd.DataFrame:
    """Rolling correlation of `base`'s returns against every other column."""
    rets = to_returns(panel)
    if base not in rets.columns:
        raise ValueError(f"base '{base}' not in panel columns {list(rets.columns)}")
    others = [c for c in rets.columns if c != base]
    out = {c: rets[base].rolling(window).corr(rets[c]) for c in others}
    return pd.DataFrame(out)


def correlation_report(panel: pd.DataFrame, base: str = "BTC") -> str:
    """Human-readable summary: 30d & 90d correlation of base vs each series."""
    if panel.empty or base not in panel.columns:
        return "correlation_report: empty panel or base missing."

    rets = to_returns(panel)
    others = [c for c in rets.columns if c != base]
    c30 = rets.tail(30).corr()[base]
    c90 = rets.tail(90).corr()[base]

    lines = [
        f"Correlation of {base} daily returns vs each series:",
        f"  {'series':<8}{'30d':>8}{'90d':>8}   regime",
        "  " + "-" * 36,
    ]
    for c in others:
        r30, r90 = c30.get(c, float("nan")), c90.get(c, float("nan"))
        # crude regime tag on the 30d reading
        if r30 != r30:  # NaN
            tag = "n/a"
        elif abs(r30) < 0.15:
            tag = "decoupled"
        elif r30 > 0.4:
            tag = "strong +"
        elif r30 < -0.4:
            tag = "strong -"
        else:
            tag = "mild " + ("+" if r30 > 0 else "-")
        lines.append(f"  {c:<8}{r30:>8.2f}{r90:>8.2f}   {tag}")

    return "\n".join(lines)


if __name__ == "__main__":
    from local_system.signals.macro import build_panel

    panel = build_panel(lookback_days=365)
    if panel.empty:
        print("NO DATA")
    else:
        print(f"panel {panel.shape[0]}d x {panel.shape[1]} series\n")
        print(correlation_report(panel, base="BTC"))
        print("\nFull 90d return-correlation matrix:")
        print(correlation_matrix(panel, window=90).round(2).to_string())
