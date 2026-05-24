"""
paper_trader.py — local paper trading loop.

Runs independently of the terminal. Reads live 1m bars from the crypto-lake-rs
parquet store, generates signals from all configured strategies, tracks paper
positions, and writes state/status.json every tick.

Run:
    uv run python -m local_system.paper_trader

The process is designed to run in the background. The terminal is just a window
into it via the /status skill — you can close and reopen the terminal freely.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
STATE_DIR = ROOT / "state"
STATUS_FILE = STATE_DIR / "status.json"
PAPER_TRADES_FILE = STATE_DIR / "paper_trades.jsonl"
STRATEGY_FILE = STATE_DIR / "strategy.yaml"

TICK_SEC = 60  # re-evaluate every 60 seconds
LOOKBACK_DAYS = 7  # bars for signal calculation


def _load_strategies():
    """Load active + challenger strategies based on state/strategy.yaml."""
    from local_system.strategies.markov import MarkovStrategy
    from local_system.strategies.rsi_meanrev import RsiMeanRevStrategy

    # Active strategy always comes from state/strategy.yaml
    active_params = {}
    if STRATEGY_FILE.exists():
        spec = yaml.safe_load(STRATEGY_FILE.read_text())
        active_params = spec.get("params", {})

    active = MarkovStrategy(params=active_params)

    # Challengers are hardcoded for now; add more here as needed
    challengers = [RsiMeanRevStrategy()]

    return active, challengers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status(
    active_name: str,
    active_position: dict,
    challenger_positions: list[dict],
    last_price: float,
    last_bar_ts: str,
    tick: int,
) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    payload = {
        "ts": _now_iso(),
        "tick": tick,
        "last_price": last_price,
        "last_bar_ts": last_bar_ts,
        "active": {
            "strategy": active_name,
            "position": active_position,
        },
        "challengers": challenger_positions,
    }
    STATUS_FILE.write_text(json.dumps(payload, indent=2))


def _write_trade(strategy_name: str, action: str, price: float, pnl_pct: float | None) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    record = {
        "ts": _now_iso(),
        "strategy": strategy_name,
        "action": action,
        "price": price,
        "pnl_pct": pnl_pct,
    }
    with open(PAPER_TRADES_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


class PaperPosition:
    """Tracks a single paper trade position for one strategy."""

    def __init__(self, strategy_name: str):
        self.name = strategy_name
        self.in_position = False
        self.entry_price = 0.0
        self.entry_ts = ""
        self.pnl_pct = 0.0
        self.total_pnl_pct = 0.0
        self.trade_count = 0

    def enter(self, price: float) -> None:
        self.in_position = True
        self.entry_price = price
        self.entry_ts = _now_iso()
        self.pnl_pct = 0.0
        _write_trade(self.name, "BUY", price, None)

    def exit(self, price: float) -> None:
        gross = (price - self.entry_price) / self.entry_price
        net = gross - 0.0024  # round-trip cost
        self.pnl_pct = net
        self.total_pnl_pct += net
        self.trade_count += 1
        self.in_position = False
        _write_trade(self.name, "SELL", price, net)

    def update_unrealised(self, price: float) -> None:
        if self.in_position and self.entry_price > 0:
            gross = (price - self.entry_price) / self.entry_price
            self.pnl_pct = gross - 0.0012  # half round-trip (entry cost only)

    def to_dict(self) -> dict:
        return {
            "in_position": self.in_position,
            "entry_price": self.entry_price,
            "entry_ts": self.entry_ts,
            "unrealised_pnl_pct": round(self.pnl_pct * 100, 3),
            "total_pnl_pct": round(self.total_pnl_pct * 100, 3),
            "trade_count": self.trade_count,
        }


async def run_loop() -> None:
    from local_system.lake_adapter import load_recent_bars

    active_strategy, challengers = _load_strategies()

    # Fit all strategies on recent history before starting the live loop
    print(f"[paper_trader] Loading {LOOKBACK_DAYS}d of bars for initial fit...", flush=True)
    df_init = load_recent_bars("BTCUSDT", n_days=LOOKBACK_DAYS * 5)
    if df_init.empty:
        print("[paper_trader] ERROR: No data in lake. Is crypto-lake-rs running?", flush=True)
        sys.exit(1)

    split = int(len(df_init) * 0.8)
    active_strategy.fit(df_init.iloc[:split])
    for c in challengers:
        c.fit(df_init.iloc[:split])

    active_pos = PaperPosition(active_strategy.name)
    challenger_positions = {c.name: PaperPosition(c.name) for c in challengers}

    tick = 0
    print(f"[paper_trader] Live loop started. Active: {active_strategy.name}", flush=True)

    while True:
        tick += 1
        try:
            df = load_recent_bars("BTCUSDT", n_days=LOOKBACK_DAYS)
            if df.empty:
                print(f"[paper_trader] tick {tick:04d} — no data, skipping", flush=True)
                await asyncio.sleep(TICK_SEC)
                continue

            price = float(df["close"].iloc[-1])
            last_bar_ts = str(df.index[-1])

            # ── Active strategy ───────────────────────────────────────────────
            sig = active_strategy.signal(df)
            if not active_pos.in_position and sig == 1:
                active_pos.enter(price)
            elif active_pos.in_position and sig != 1:
                active_pos.exit(price)
            active_pos.update_unrealised(price)

            # ── Challengers ───────────────────────────────────────────────────
            challenger_states = []
            for c in challengers:
                pos = challenger_positions[c.name]
                csig = c.signal(df)
                if not pos.in_position and csig == 1:
                    pos.enter(price)
                elif pos.in_position and csig != 1:
                    pos.exit(price)
                pos.update_unrealised(price)
                challenger_states.append({"strategy": c.name, "position": pos.to_dict()})

            _write_status(
                active_strategy.name,
                active_pos.to_dict(),
                challenger_states,
                price,
                last_bar_ts,
                tick,
            )

            print(
                f"[paper_trader] tick {tick:04d} | price={price:,.2f} | "
                f"active={'LONG' if active_pos.in_position else 'FLAT'} "
                f"pnl={active_pos.pnl_pct * 100:+.2f}%",
                flush=True,
            )

        except Exception as exc:
            print(f"[paper_trader] tick {tick:04d} ERROR: {exc}", flush=True)

        await asyncio.sleep(TICK_SEC)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
