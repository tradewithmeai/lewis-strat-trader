"""
/status — terminal dashboard for the local paper trading system.

Reads state/status.json and state/comparison.json and prints a summary.
Does not require the paper_trader loop to be running — shows last known state.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
STATE_DIR = ROOT / "state"


def _age(ts_iso: str) -> str:
    """Human-readable age of a timestamp."""
    try:
        ts = datetime.fromisoformat(ts_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - ts).total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return "?"


def print_status() -> None:
    status_file = STATE_DIR / "status.json"
    comparison_file = STATE_DIR / "comparison.json"

    print()
    print("=" * 60)
    print("  PAPER TRADING STATUS")
    print("=" * 60)

    if not status_file.exists():
        print("  No status.json found. Is paper_trader running?")
        print("  Start with: uv run python -m local_system.paper_trader")
        print()
        return

    status = json.loads(status_file.read_text())
    ts = status.get("ts", "?")
    tick = status.get("tick", "?")
    price = status.get("last_price", 0)
    last_bar = status.get("last_bar_ts", "?")

    print(f"  Last update : {_age(ts)} ({ts[:19]}Z)")
    print(f"  Tick        : {tick}")
    print(f"  BTCUSDT     : ${price:,.2f}  (bar: {last_bar[:16]})")
    print()

    # Active strategy
    active = status.get("active", {})
    aname = active.get("strategy", "?")
    apos = active.get("position", {})
    side = "LONG" if apos.get("in_position") else "FLAT"
    upnl = apos.get("unrealised_pnl_pct", 0)
    tpnl = apos.get("total_pnl_pct", 0)
    n_trades = apos.get("trade_count", 0)

    print(f"  ACTIVE  [{aname}]")
    print(f"    Position  : {side}")
    if apos.get("in_position"):
        entry = apos.get("entry_price", 0)
        print(f"    Entry     : ${entry:,.2f}")
        colour = "\033[92m" if upnl >= 0 else "\033[91m"
        print(f"    Unrealised: {colour}{upnl:+.2f}%\033[0m")
    print(f"    Total PnL : {tpnl:+.2f}%  ({n_trades} trades)")
    print()

    # Challengers
    challengers = status.get("challengers", [])
    if challengers:
        print("  CHALLENGERS")
        for c in challengers:
            cname = c.get("strategy", "?")
            cpos = c.get("position", {})
            cside = "LONG" if cpos.get("in_position") else "FLAT"
            cupnl = cpos.get("unrealised_pnl_pct", 0)
            ctpnl = cpos.get("total_pnl_pct", 0)
            cn_trades = cpos.get("trade_count", 0)
            print(f"    [{cname}]  {cside}  pnl={ctpnl:+.2f}%  trades={cn_trades}")
            if cpos.get("in_position"):
                colour = "\033[92m" if cupnl >= 0 else "\033[91m"
                print(f"      Unrealised: {colour}{cupnl:+.2f}%\033[0m")
        print()

    # Traffic light
    if comparison_file.exists():
        comparison = json.loads(comparison_file.read_text())
        print("  TRAFFIC LIGHT")
        lights = {
            "GREEN": "\033[92m[G]\033[0m",
            "ORANGE": "\033[93m[O]\033[0m",
            "RED": "\033[91m[R]\033[0m",
        }
        for name, entry in sorted(comparison.items()):
            light = entry.get("light", "?")
            score = entry.get("score", 0)
            days = entry.get("days_beating", 0) or 0
            marker = " <-- ACTIVE" if entry.get("is_active") else f"  ({days}d at par)"
            dot = lights.get(light, "?")
            print(f"    {dot} {light:<7} {name:<25} score={score:.3f}{marker}")
        print()

    # Pending alerts
    alerts_file = STATE_DIR / "alerts.jsonl"
    if alerts_file.exists():
        lines = [l for l in alerts_file.read_text().splitlines() if l.strip()]
        if lines:
            last_alert = json.loads(lines[-1])
            print("  \033[93m*** ALERT ***\033[0m")
            print(f"  {last_alert.get('message', '')}")
            print(f"  Action: {last_alert.get('action_required', '')}")
            print()

    print("=" * 60)


if __name__ == "__main__":
    print_status()
