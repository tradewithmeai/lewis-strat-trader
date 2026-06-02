"""
trump_overlay.py — bar-aligned Trump vol-risk overlay feature.

Converts the event-time burst table (trump_events.parquet) into a boolean
column on an hourly bar DataFrame:

    trump_vol_active   True for the 4h after any market-relevant burst

The 4h window comes from the event-study finding: forward realized vol is
elevated at the 1-4h horizon after market-relevant bursts (BTC +5.1bp/4h
p=0.008, ETH similar, SOL in-office p=0.033), surviving a trailing-vol-matched
null (docs/TRUMP_EVENT_STUDY.md).

Intended use: entry-suppression overlay in the backtester — pause new entries
during the elevated-vol window; hold existing positions normally. This is a
RISK overlay, not a directional alpha signal. The directional results (china ->
neg) are too small and co-linear to use as alpha without repeating the
bollinger/regime_bb overfitting failure.

Usage:
    from local_system.signals.trump_overlay import add_overlay
    bars = add_overlay(bars)    # adds trump_vol_active column in-place
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

EVENTS_PATH = Path("state/signals/trump_events.parquet")
VOL_WINDOW_H = 4  # hours of elevated-vol following a burst


def add_overlay(bars: pd.DataFrame) -> pd.DataFrame:
    """Add ``trump_vol_active`` column to *bars* (hourly, UTC index).

    True at any bar that falls within VOL_WINDOW_H hours after a
    market-relevant, non-noise burst. Returns a copy.
    """
    if not EVENTS_PATH.exists():
        bars = bars.copy()
        bars["trump_vol_active"] = False
        return bars

    ev = pd.read_parquet(EVENTS_PATH)
    # Use market-relevant, non-noise bursts — same population as the event study
    bursts = (
        ev[ev.market_relevant & ~ev.is_noise]
        .groupby("burst_id")["ts"]
        .min()
        .reset_index(drop=True)
    )
    burst_hours = pd.to_datetime(bursts, utc=True).dt.floor("h")

    # Mark the event bar plus the next VOL_WINDOW_H - 1 bars
    active = pd.Series(False, index=bars.index)
    for h in burst_hours:
        end = h + pd.Timedelta(hours=VOL_WINDOW_H)
        active.loc[(bars.index >= h) & (bars.index < end)] = True

    bars = bars.copy()
    bars["trump_vol_active"] = active.reindex(bars.index, fill_value=False)
    return bars
