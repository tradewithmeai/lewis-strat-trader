"""
live_board.py — traffic-light rules for the LIVE paper-trade comparison.

This replaces the old role-based, backtest-driven scheme (where "green" merely
meant "the active strategy"). Colours now reflect real live performance:

  GREEN  — in profit (equity > start capital), past warm-up, not in the cull zone
  RED    — "about to be excluded": the worst-ranked CULL_BOTTOM strategies that
           are past warm-up (relative cull — keeps pressure on even in a bull run)
  ORANGE — everything else: still warming up (potential), or established but
           middling / not in the cull zone

Warm-up guard: a fresh $1,000 account is pure noise for its first days, so a
strategy cannot go RED until it has a real track record (WARMUP_DAYS live OR
WARMUP_TRADES closed trades). Until then it is ORANGE regardless of P&L.

Ranking is by equity (realised balance + open unrealised), highest = best.
"""

from __future__ import annotations

from datetime import datetime, timezone

START_CAPITAL = 1000.0

WARMUP_DAYS = 14          # days live before a strategy can be judged for the cull
WARMUP_TRADES = 20        # ...or this many closed trades, whichever comes first
CULL_BOTTOM = 3           # the worst N established strategies are RED
# Only cull once there are clearly more established strategies than cull slots,
# otherwise an early board would paint half the field red.
MIN_ESTABLISHED_TO_CULL = CULL_BOTTOM + 2


def _days_live(start_ts: str | None, now: datetime) -> float:
    if not start_ts:
        return 0.0
    try:
        start = datetime.fromisoformat(start_ts)
    except ValueError:
        return 0.0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return max(0.0, (now - start).total_seconds() / 86400.0)


def is_established(acct: dict, now: datetime | None = None) -> bool:
    """A strategy has enough track record to be judged (else it stays orange)."""
    now = now or datetime.now(timezone.utc)
    return (
        _days_live(acct.get("start_ts"), now) >= WARMUP_DAYS
        or int(acct.get("trade_count", 0)) >= WARMUP_TRADES
    )


def assign_lights(accounts: dict, now: datetime | None = None) -> dict:
    """Given {name: account_dict}, return {name: "GREEN"|"ORANGE"|"RED"}.

    account_dict must carry: equity (float), start_ts (iso), trade_count (int).
    """
    now = now or datetime.now(timezone.utc)
    established = [n for n, a in accounts.items() if is_established(a, now)]

    cull: set[str] = set()
    if len(established) >= MIN_ESTABLISHED_TO_CULL:
        ranked = sorted(established, key=lambda n: accounts[n].get("equity", START_CAPITAL))
        cull = set(ranked[:CULL_BOTTOM])

    lights: dict[str, str] = {}
    for name, acct in accounts.items():
        if name not in established:
            lights[name] = "ORANGE"          # still proving itself
        elif name in cull:
            lights[name] = "RED"             # bottom of the pack — about to be excluded
        elif acct.get("equity", START_CAPITAL) > START_CAPITAL:
            lights[name] = "GREEN"           # in profit
        else:
            lights[name] = "ORANGE"          # established but flat/slightly down, not culled
    return lights
