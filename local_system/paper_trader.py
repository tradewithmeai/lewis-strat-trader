"""
paper_trader.py — LIVE paper-trade comparison loop.

Runs every strategy in the registry as an independent **persistent $1,000 paper
account** trading the real-time feed forward. Each account compounds, survives
restarts (state is reloaded from disk), and accumulates over real wall-clock time
— this live forward record IS out-of-sample by construction, so there is no
train/test split. (The backtester/`reflect` is now only the "lab" that vets
proposed new strategies before they earn a live account.)

Reads recent 1m bars from the crypto-lake-rs parquet store, resamples to 1h
(matching the strategy lookbacks), generates signals, tracks paper positions
(long AND short, with stop-loss), updates each account's balance on every closed
trade, and writes:

    state/paper_accounts.json   the persistent live ledger (source of the board)
    state/status.json           a per-tick snapshot (for the /status skill)

A buy-and-hold BTC benchmark is tracked alongside so "in profit" is honest.

Run:  uv run python -m local_system.paper_trader   (designed to run as a service)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from local_system.live_board import START_CAPITAL, assign_lights

ROOT = Path(__file__).parent.parent
STATE_DIR = ROOT / "state"
STATUS_FILE = STATE_DIR / "status.json"
ACCOUNTS_FILE = STATE_DIR / "paper_accounts.json"
PAPER_TRADES_FILE = STATE_DIR / "paper_trades.jsonl"

SYMBOL = "BTCUSDT"
TICK_SEC = 300            # re-evaluate every 5 minutes
HISTORY_DAYS = 150        # trailing window: enough for 90d regime gate + lookbacks
ROUND_TRIP_COST = 0.0024  # 0.1% taker x2 + 2bps slippage x2 (matches backtester)

# Regime detection (matches local_system.cli.walkforward)
_REGIME_WINDOW = 90
_BULL_THRESHOLD = 0.10
_BEAR_THRESHOLD = 0.10


# ── Config ──────────────────────────────────────────────────────────────────


def _all_strategies():
    """Instantiate every strategy in the registry (the full live field)."""
    from local_system.strategies.registry import get_strategy, list_strategies

    out = []
    for name in list_strategies():
        try:
            out.append(get_strategy(name))
        except (ValueError, ImportError) as exc:
            print(f"[paper_trader] skipping '{name}': {exc}", flush=True)
    return out


def _directional() -> bool:
    """Optional global regime gate, from state/strategy.yaml (default off)."""
    f = STATE_DIR / "strategy.yaml"
    if f.exists():
        try:
            import yaml

            return bool((yaml.safe_load(f.read_text()) or {}).get("directional", False))
        except Exception:
            return False
    return False


# ── Regime gate (causal) ─────────────────────────────────────────────────────


def _classify_regime(df_1h: pd.DataFrame) -> str:
    daily = df_1h["close"].resample("1D").last().dropna()
    if len(daily) < _REGIME_WINDOW + 1:
        return "ranging"
    roll_ret = daily.iloc[-1] / daily.iloc[-(_REGIME_WINDOW + 1)] - 1.0
    if roll_ret > _BULL_THRESHOLD:
        return "bull"
    if roll_ret < -_BEAR_THRESHOLD:
        return "bear"
    return "ranging"


def _apply_directional(sig: int, regime: str) -> int:
    if regime == "bull" and sig == -1:
        return 0
    if regime == "bear" and sig == 1:
        return 0
    return sig


# ── IO ────────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, text: str) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def _write_trade(name: str, action: str, side: str, price: float, pnl_pct: float | None) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    with open(PAPER_TRADES_FILE, "a") as f:
        f.write(json.dumps({
            "ts": _now_iso(), "strategy": name, "action": action,
            "side": side, "price": price, "pnl_pct": pnl_pct,
        }) + "\n")


# ── Persistent paper account (balance + open position) ───────────────────────


class PaperAccount:
    """A persistent $1,000 account for one strategy. Long/short, stop-loss,
    compounding balance. Serialises to/from the ledger so it survives restarts."""

    def __init__(self, name: str, stop_loss_pct: float = 0.0):
        self.name = name
        self.stop_loss_frac = (stop_loss_pct / 100.0) if stop_loss_pct else 0.0
        self.balance = START_CAPITAL          # realised equity (compounded on close)
        self.start_ts = _now_iso()
        self.side = 0                         # 0 flat, +1 long, -1 short
        self.entry_price = 0.0
        self.entry_ts = ""
        self.trade_count = 0
        self.win_count = 0
        self.unrealised_pct = 0.0             # open-trade mark, for display only

    # -- persistence --
    def load(self, d: dict) -> None:
        self.balance = float(d.get("balance", START_CAPITAL))
        self.start_ts = d.get("start_ts") or self.start_ts
        side_raw = d.get("side", 0)  # ledger stores side as a display string ("long"/...)
        self.side = (
            {"long": 1, "short": -1, "flat": 0}.get(side_raw, 0)
            if isinstance(side_raw, str)
            else int(side_raw)
        )
        self.entry_price = float(d.get("entry_price", 0.0))
        self.entry_ts = d.get("entry_ts", "")
        self.trade_count = int(d.get("trade_count", 0))
        self.win_count = int(d.get("win_count", 0))

    @property
    def in_position(self) -> bool:
        return self.side != 0

    @property
    def equity(self) -> float:
        """Balance marked to the open position (realised * (1 + unrealised))."""
        return round(self.balance * (1.0 + self.unrealised_pct), 2)

    def enter(self, price: float, side: int) -> None:
        self.side = side
        self.entry_price = price
        self.entry_ts = _now_iso()
        self.unrealised_pct = 0.0
        _write_trade(self.name, "ENTER", "long" if side == 1 else "short", price, None)

    def exit(self, price: float, reason: str) -> None:
        gross = self.side * (price - self.entry_price) / self.entry_price
        net = gross - ROUND_TRIP_COST
        self.balance = round(self.balance * (1.0 + net), 2)   # compound
        self.trade_count += 1
        if net > 0:
            self.win_count += 1
        _write_trade(self.name, f"EXIT_{reason}",
                     "long" if self.side == 1 else "short", price, net)
        self.side = 0
        self.entry_price = 0.0
        self.entry_ts = ""
        self.unrealised_pct = 0.0

    def stop_hit(self, price: float) -> bool:
        if not self.in_position or not self.stop_loss_frac:
            return False
        if self.side == 1:
            return price <= self.entry_price * (1 - self.stop_loss_frac)
        return price >= self.entry_price * (1 + self.stop_loss_frac)

    def update_unrealised(self, price: float) -> None:
        if self.in_position and self.entry_price > 0:
            gross = self.side * (price - self.entry_price) / self.entry_price
            self.unrealised_pct = gross - ROUND_TRIP_COST / 2  # entry cost only, while open
        else:
            self.unrealised_pct = 0.0

    def to_dict(self) -> dict:
        wr = (self.win_count / self.trade_count) if self.trade_count else 0.0
        eq = self.equity
        return {
            "balance": round(self.balance, 2),
            "equity": eq,
            "pnl": round(eq - START_CAPITAL, 2),
            "return_pct": round((eq / START_CAPITAL - 1.0) * 100.0, 2),
            "start_ts": self.start_ts,
            "side": {1: "long", -1: "short", 0: "flat"}[self.side],
            "in_position": self.in_position,
            "entry_price": round(self.entry_price, 2),
            "entry_ts": self.entry_ts,
            "unrealised_pnl_pct": round(self.unrealised_pct * 100, 3),
            "trade_count": self.trade_count,
            "win_count": self.win_count,  # persisted so win-rate survives a restart
            "win_rate": round(wr, 3),
        }


def _sync_strategy_flat(strategy, ts: pd.Timestamp) -> None:
    if hasattr(strategy, "_in_position"):
        strategy._in_position = False
    if hasattr(strategy, "_side"):
        strategy._side = 0
    if hasattr(strategy, "notify_stop"):
        try:
            strategy.notify_stop(ts)
        except Exception:
            pass


def _step_strategy(strategy, acct: PaperAccount, df_1h, price, directional, regime, now_ts):
    """Advance one strategy by one tick, mirroring backtester execution order."""
    if acct.stop_hit(price):
        acct.exit(price, "stop")
        _sync_strategy_flat(strategy, now_ts)
        return
    sig = strategy.signal(df_1h)
    if directional:
        sig = _apply_directional(sig, regime)
    if not acct.in_position:
        if sig in (1, -1):
            acct.enter(price, sig)
    elif sig != acct.side:
        acct.exit(price, "signal")


# ── Ledger load/save ──────────────────────────────────────────────────────────


def _load_ledger(strategies) -> tuple[dict, dict]:
    """Build {name: PaperAccount} (restoring saved state) and the benchmark dict."""
    saved = {}
    if ACCOUNTS_FILE.exists():
        try:
            saved = json.loads(ACCOUNTS_FILE.read_text())
        except Exception as exc:
            print(f"[paper_trader] could not read ledger ({exc}); starting fresh", flush=True)

    saved_acc = saved.get("accounts", {})
    accounts: dict[str, PaperAccount] = {}
    for s in strategies:
        sl = float(getattr(s, "params", {}).get("stop_loss_pct", 0) or 0)
        acct = PaperAccount(s.name, sl)
        if s.name in saved_acc:
            acct.load(saved_acc[s.name])
        accounts[s.name] = acct

    benchmark = saved.get("benchmark", {})  # {start_ts, start_price, ...}
    return accounts, benchmark


def _save_ledger(accounts: dict, benchmark: dict, price: float, bar_ts: str,
                 regime: str, extra_accounts: dict | None = None) -> None:
    acc_dicts = {name: a.to_dict() for name, a in accounts.items()}
    if extra_accounts:
        acc_dicts.update(extra_accounts)   # portfolio books (e.g. xsec_momentum)
    lights = assign_lights(acc_dicts)
    for name, light in lights.items():
        acc_dicts[name]["light"] = light

    payload = {
        "meta": {
            "symbol": SYMBOL,
            "start_capital": START_CAPITAL,
            "last_tick_ts": _now_iso(),
            "last_bar_ts": bar_ts,
            "last_price": round(price, 2),
            "regime": regime,
        },
        "accounts": acc_dicts,
        "benchmark": benchmark,
    }
    # persist the portfolio book's inception so it's stable across restarts
    if extra_accounts:
        for a in extra_accounts.values():
            if a.get("kind") == "portfolio" and a.get("start_ts"):
                payload["portfolio_inception"] = a["start_ts"]
                break
    _atomic_write(ACCOUNTS_FILE, json.dumps(payload, indent=2))
    # compact per-tick snapshot for the /status skill
    _atomic_write(STATUS_FILE, json.dumps({
        "ts": _now_iso(), "last_price": round(price, 2), "last_bar_ts": bar_ts,
        "regime": regime, "accounts": acc_dicts, "benchmark": benchmark,
    }, indent=2))


def _update_benchmark(benchmark: dict, price: float) -> dict:
    """Buy-and-hold BTC from the board's inception."""
    if not benchmark.get("start_price"):
        benchmark = {"start_ts": _now_iso(), "start_price": round(price, 2)}
    bal = round(START_CAPITAL * (price / benchmark["start_price"]), 2)
    benchmark["balance"] = bal
    benchmark["return_pct"] = round((price / benchmark["start_price"] - 1.0) * 100.0, 2)
    benchmark["last_price"] = round(price, 2)
    return benchmark


# ── Data ───────────────────────────────────────────────────────────────────────


def _load_history():
    """Trailing HISTORY_DAYS of 1m bars resampled to 1h (clean backfill + live rollup)."""
    from local_system.signals.live_rollup import load_history_hybrid

    end = date.today()
    start = end - timedelta(days=HISTORY_DAYS)
    return load_history_hybrid(SYMBOL, start, end)


# ── Main loop ──────────────────────────────────────────────────────────────────


async def run_loop() -> None:
    directional = _directional()
    strategies = _all_strategies()

    print(f"[paper_trader] Loading {HISTORY_DAYS}d of bars for initial fit...", flush=True)
    df_init = _load_history()
    if df_init.empty:
        print("[paper_trader] ERROR: No data in lake. Is crypto-lake-rs running?", flush=True)
        sys.exit(1)

    # No train/test split: fit on the full available history (live forward IS OOS).
    for s in strategies:
        try:
            s.fit(df_init)
        except Exception as exc:
            print(f"[paper_trader] fit failed for {s.name}: {exc}", flush=True)

    accounts, benchmark = _load_ledger(strategies)
    print(
        f"[paper_trader] Live board started: {len(accounts)} accounts | "
        f"directional={'ON' if directional else 'off'} | "
        f"resuming={'yes' if ACCOUNTS_FILE.exists() else 'fresh'}",
        flush=True,
    )

    # Cross-sectional momentum portfolio book — refreshed ~hourly (heavy: loads the
    # universe daily panel). Inception persisted in the ledger so it's stable.
    lake_root = os.environ.get("LAKE_ROOT", "")
    portfolio_inception = (
        (json.loads(ACCOUNTS_FILE.read_text()).get("portfolio_inception") if ACCOUNTS_FILE.exists() else None)
        or _now_iso()
    )
    portfolio_cache: dict = {}
    portfolio_refresh_every = 12  # ticks (~1h at 300s)

    tick = 0
    while True:
        tick += 1
        try:
            df = _load_history()
            if df.empty:
                print(f"[paper_trader] tick {tick:04d} — no data, skipping", flush=True)
                await asyncio.sleep(TICK_SEC)
                continue

            price = float(df["close"].iloc[-1])
            now_ts = df.index[-1]
            bar_ts = str(now_ts)
            regime = _classify_regime(df)

            for s in strategies:
                acct = accounts[s.name]
                _step_strategy(s, acct, df, price, directional, regime, now_ts)
                acct.update_unrealised(price)

            benchmark = _update_benchmark(benchmark, price)

            # Refresh the cross-sectional momentum book on the first tick and ~hourly
            if lake_root and (tick == 1 or tick % portfolio_refresh_every == 0):
                try:
                    from local_system.live_portfolio import NAME as PF_NAME, compute_book
                    book = compute_book(portfolio_inception, lake_root)
                    if book:
                        portfolio_cache = {PF_NAME: book}
                except Exception as pf_exc:  # noqa: BLE001
                    print(f"[paper_trader] portfolio book refresh failed: {pf_exc}", flush=True)

            _save_ledger(accounts, benchmark, price, bar_ts, regime,
                         extra_accounts=portfolio_cache or None)

            leader = max(accounts.values(), key=lambda a: a.equity)
            print(
                f"[paper_trader] tick {tick:04d} | price={price:,.2f} | regime={regime} | "
                f"leader={leader.name} ${leader.equity:,.2f} | "
                f"bench ${benchmark.get('balance', START_CAPITAL):,.2f}",
                flush=True,
            )

            try:
                from local_system.signals.trump_alert import check_and_alert
                check_and_alert()
            except Exception as alert_exc:  # noqa: BLE001
                print(f"[paper_trader] trump_alert check failed: {alert_exc}", flush=True)

        except Exception as exc:
            print(f"[paper_trader] tick {tick:04d} ERROR: {exc}", flush=True)

        await asyncio.sleep(TICK_SEC)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
