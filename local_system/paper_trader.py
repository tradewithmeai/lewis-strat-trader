"""
paper_trader.py — local paper trading loop.

Runs independently of the terminal. Reads recent 1m bars from the crypto-lake-rs
parquet store, resamples to 1h (matching the backtest/reflect convention),
generates signals from the configured active strategy + all challengers, tracks
paper positions (long AND short, with stop-loss), and writes state/status.json
every tick.

Configuration is read from state/ at startup:
    state/strategy.yaml     active strategy NAME + params (+ optional directional flag)
    state/challengers.yaml  list of challenger strategy names

Both are resolved through local_system.strategies.registry, so whatever you set
as the active strategy is what actually runs — no hardcoding.

Directional regime gate (optional, strategy.yaml `directional: true`):
    Each tick, the trailing 90-day return classifies the market as bull / bear /
    ranging (the same causal rule the walk-forward uses). When enabled, bull
    suppresses short signals and bear suppresses long signals — the live mirror
    of the per-fold directional bias. Default off (no behaviour change).

Run:
    uv run python -m local_system.paper_trader

Designed to run in the background. The terminal is just a window into it via the
/status skill — close and reopen freely.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent
STATE_DIR = ROOT / "state"
STATUS_FILE = STATE_DIR / "status.json"
PAPER_TRADES_FILE = STATE_DIR / "paper_trades.jsonl"
STRATEGY_FILE = STATE_DIR / "strategy.yaml"
CHALLENGERS_FILE = STATE_DIR / "challengers.yaml"

TICK_SEC = 300  # hourly strategies — re-evaluate every 5 minutes
HISTORY_DAYS = 150  # trailing window: enough for 90d regime gate + strategy lookbacks
ROUND_TRIP_COST = 0.0024  # 0.1% taker x2 + 2bps slippage x2 (matches backtester)

# Regime detection (matches local_system.cli.walkforward)
_REGIME_WINDOW = 90  # days
_BULL_THRESHOLD = 0.10
_BEAR_THRESHOLD = 0.10


# ── Config loading ────────────────────────────────────────────────────────────


def _load_config() -> tuple[str, dict, bool, list[str]]:
    """Return (active_name, active_params, directional, challenger_names)."""
    active_name = "markov_regime"
    active_params: dict = {}
    directional = False
    if STRATEGY_FILE.exists():
        spec = yaml.safe_load(STRATEGY_FILE.read_text()) or {}
        active_name = spec.get("strategy", active_name)
        active_params = spec.get("params", {}) or {}
        directional = bool(spec.get("directional", False))

    challenger_names: list[str] = []
    if CHALLENGERS_FILE.exists():
        cspec = yaml.safe_load(CHALLENGERS_FILE.read_text()) or {}
        challenger_names = cspec.get("challengers", []) or []

    # Don't run the active strategy twice if it also appears in challengers
    challenger_names = [n for n in challenger_names if n != active_name]
    return active_name, active_params, directional, challenger_names


def _make_strategies(active_name: str, active_params: dict, challenger_names: list[str]):
    """Instantiate active + challengers via the registry."""
    from local_system.strategies.registry import get_strategy

    active = get_strategy(active_name, active_params)
    challengers = []
    for name in challenger_names:
        try:
            challengers.append(get_strategy(name))
        except (ValueError, ImportError) as exc:
            print(f"[paper_trader] skipping challenger '{name}': {exc}", flush=True)
    return active, challengers


# ── Regime gate (causal) ────────────────────────────────────────────────────


def _classify_regime(df_1h: pd.DataFrame) -> str:
    """Classify the current market via trailing 90-day return on daily closes.

    Backward-looking only (uses bars up to now), so it is safe to use live.
    """
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
    """Suppress shorts in bull, longs in bear. Ranging unconstrained."""
    if regime == "bull" and sig == -1:
        return 0
    if regime == "bear" and sig == 1:
        return 0
    return sig


# ── Status / trade IO ──────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status(payload: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, indent=2))


def _write_trade(
    strategy_name: str, action: str, side: str, price: float, pnl_pct: float | None
) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    record = {
        "ts": _now_iso(),
        "strategy": strategy_name,
        "action": action,
        "side": side,
        "price": price,
        "pnl_pct": pnl_pct,
    }
    with open(PAPER_TRADES_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Position tracking (long + short + stop-loss) ─────────────────────────────


class PaperPosition:
    """Tracks a single paper position for one strategy. Supports long and short."""

    def __init__(self, strategy_name: str, stop_loss_pct: float = 0.0):
        self.name = strategy_name
        self.side = 0  # 0 flat, +1 long, -1 short
        self.entry_price = 0.0
        self.entry_ts = ""
        self.pnl_pct = 0.0
        self.total_pnl_pct = 0.0
        self.trade_count = 0
        self.win_count = 0
        self.stop_loss_frac = (stop_loss_pct / 100.0) if stop_loss_pct else 0.0

    @property
    def in_position(self) -> bool:
        return self.side != 0

    def enter(self, price: float, side: int) -> None:
        self.side = side
        self.entry_price = price
        self.entry_ts = _now_iso()
        self.pnl_pct = 0.0
        _write_trade(self.name, "ENTER", "long" if side == 1 else "short", price, None)

    def exit(self, price: float, reason: str) -> float:
        gross = self.side * (price - self.entry_price) / self.entry_price
        net = gross - ROUND_TRIP_COST
        side_str = "long" if self.side == 1 else "short"
        self.pnl_pct = net
        self.total_pnl_pct += net
        self.trade_count += 1
        if net > 0:
            self.win_count += 1
        _write_trade(self.name, f"EXIT_{reason}", side_str, price, net)
        self.side = 0
        return net

    def stop_hit(self, price: float) -> bool:
        if not self.in_position or not self.stop_loss_frac:
            return False
        if self.side == 1:
            return price <= self.entry_price * (1 - self.stop_loss_frac)
        return price >= self.entry_price * (1 + self.stop_loss_frac)

    def update_unrealised(self, price: float) -> None:
        if self.in_position and self.entry_price > 0:
            gross = self.side * (price - self.entry_price) / self.entry_price
            self.pnl_pct = gross - ROUND_TRIP_COST / 2  # entry cost only, while open

    def to_dict(self) -> dict:
        wr = (self.win_count / self.trade_count) if self.trade_count else 0.0
        return {
            "side": {1: "long", -1: "short", 0: "flat"}[self.side],
            "in_position": self.in_position,
            "entry_price": round(self.entry_price, 2),
            "entry_ts": self.entry_ts,
            "unrealised_pnl_pct": round(self.pnl_pct * 100, 3),
            "total_pnl_pct": round(self.total_pnl_pct * 100, 3),
            "trade_count": self.trade_count,
            "win_rate": round(wr, 3),
        }


def _sync_strategy_flat(strategy, ts: pd.Timestamp) -> None:
    """Tell a stateful strategy it has been force-exited (stop-loss)."""
    if hasattr(strategy, "_in_position"):
        strategy._in_position = False
    if hasattr(strategy, "_side"):
        strategy._side = 0
    if hasattr(strategy, "notify_stop"):
        try:
            strategy.notify_stop(ts)
        except Exception:
            pass


def _step_strategy(
    strategy,
    pos: PaperPosition,
    df_1h: pd.DataFrame,
    price: float,
    directional: bool,
    regime: str,
    now_ts: pd.Timestamp,
) -> None:
    """Advance one strategy by one tick, mirroring backtester execution order.

    Stop-loss is checked first (and short-circuits the signal call, so a stateful
    strategy's signal() is invoked at most once per tick — matching the backtester
    which `continue`s after a stop).
    """
    # 1. Stop-loss (price-based, using the latest close)
    if pos.stop_hit(price):
        pos.exit(price, "stop")
        _sync_strategy_flat(strategy, now_ts)
        return

    # 2. Signal (called exactly once)
    sig = strategy.signal(df_1h)
    if directional:
        sig = _apply_directional(sig, regime)

    if not pos.in_position:
        if sig == 1:
            pos.enter(price, 1)
        elif sig == -1:
            pos.enter(price, -1)
    else:
        # Exit when the signal no longer agrees with the open side
        if sig != pos.side:
            pos.exit(price, "signal")


# ── Main loop ────────────────────────────────────────────────────────────────


def _load_history():
    """Load a trailing HISTORY_DAYS window of 1m bars resampled to 1h."""
    from local_system.lake_adapter import load_bars, resample_ohlcv

    end = date.today()
    start = end - timedelta(days=HISTORY_DAYS)
    # Hybrid loader: clean backfill for the bulk + a per-day 1h rollup of the
    # live 1s days for real-time freshness. The live partitions have multiple
    # parquet-corruption modes (truncated footers AND corrupt thrift metadata,
    # the latter reported by DuckDB with no file path) plus ~1140 files/day, so
    # reading them directly per tick is neither robust nor fast. live_rollup
    # reads each live day once (per-file, skipping corrupt files), aggregates to
    # 1h, and caches it; this stitches backfill + rollup into a clean series.
    from local_system.signals.live_rollup import load_history_hybrid

    return load_history_hybrid("BTCUSDT", start, end)


async def run_loop() -> None:
    active_name, active_params, directional, challenger_names = _load_config()
    active, challengers = _make_strategies(active_name, active_params, challenger_names)

    print(f"[paper_trader] Loading {HISTORY_DAYS}d of bars for initial fit...", flush=True)
    df_init = _load_history()
    if df_init.empty:
        print("[paper_trader] ERROR: No data in lake. Is crypto-lake-rs running?", flush=True)
        sys.exit(1)

    split = int(len(df_init) * 0.8)
    active.fit(df_init.iloc[:split])
    for c in challengers:
        c.fit(df_init.iloc[:split])

    def _sl(strat) -> float:
        return float(strat.params.get("stop_loss_pct", 0) or 0)

    active_pos = PaperPosition(active.name, _sl(active))
    challenger_pos = {c.name: PaperPosition(c.name, _sl(c)) for c in challengers}

    tick = 0
    dir_tag = "ON" if directional else "off"
    print(
        f"[paper_trader] Live loop started. Active: {active.name} | "
        f"challengers: {[c.name for c in challengers]} | directional: {dir_tag}",
        flush=True,
    )

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
            last_bar_ts = str(now_ts)
            regime = _classify_regime(df)

            # Active
            _step_strategy(active, active_pos, df, price, directional, regime, now_ts)
            active_pos.update_unrealised(price)

            # Challengers
            challenger_states = []
            for c in challengers:
                pos = challenger_pos[c.name]
                _step_strategy(c, pos, df, price, directional, regime, now_ts)
                pos.update_unrealised(price)
                challenger_states.append({"strategy": c.name, "position": pos.to_dict()})

            _write_status(
                {
                    "ts": _now_iso(),
                    "tick": tick,
                    "last_price": price,
                    "last_bar_ts": last_bar_ts,
                    "regime": regime,
                    "directional": directional,
                    "active": {"strategy": active.name, "position": active_pos.to_dict()},
                    "challengers": challenger_states,
                }
            )

            print(
                f"[paper_trader] tick {tick:04d} | price={price:,.2f} | regime={regime} | "
                f"active={active_pos.to_dict()['side']} "
                f"pnl={active_pos.pnl_pct * 100:+.2f}% total={active_pos.total_pnl_pct * 100:+.2f}%",
                flush=True,
            )

            # Trump post alert check — polls live feed every 5 min (rate-gated
            # inside trump_alert); no-ops fast on most ticks. Observational only.
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
