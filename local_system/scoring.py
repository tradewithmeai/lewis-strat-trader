"""
scoring.py — composite score and traffic light promotion system.

Traffic light rules:
  Active strategy starts GREEN.
  Challengers start RED.
  RED  → ORANGE : challenger composite score >= active for 7 consecutive days
  ORANGE → GREEN: challenger stays at par for 14 consecutive days
  GREEN challenger → write alert to state/alerts.jsonl (human decides to switch)

Claude cannot switch strategies — it can only alert.

Composite score = Sharpe×0.4 + win_rate×0.3 + dd_score×0.3
  dd_score = max(0, 1 - max_drawdown / MAX_DD_CAP)
  (higher is better; capped so a 20%+ drawdown scores 0)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from local_system.backtester import BacktestResult

MAX_DD_CAP = 0.20  # 20% max drawdown = score of 0
STATE_DIR = Path(__file__).parent.parent / "state"
COMPARISON_FILE = STATE_DIR / "comparison.json"
ALERTS_FILE = STATE_DIR / "alerts.jsonl"

# Days a challenger must beat active before promotion
DAYS_RED_TO_ORANGE = 7
DAYS_ORANGE_TO_GREEN = 14


def composite_score(result: BacktestResult) -> float:
    """Single number in [0, 1+] representing risk-adjusted performance."""
    sharpe_norm = max(result.sharpe, 0) / 3.0  # normalise: Sharpe 3 = full score
    win_norm = result.win_rate
    dd_score = max(0.0, 1.0 - result.max_drawdown / MAX_DD_CAP)
    return sharpe_norm * 0.4 + win_norm * 0.3 + dd_score * 0.3


def load_comparison() -> dict:
    """Load current traffic light state from state/comparison.json."""
    if not COMPARISON_FILE.exists():
        return {}
    return json.loads(COMPARISON_FILE.read_text())


def save_comparison(state: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    COMPARISON_FILE.write_text(json.dumps(state, indent=2, default=str))


def update_traffic_light(
    strategy_name: str,
    result: BacktestResult,
    active_strategy_name: str,
    active_result: BacktestResult,
) -> str:
    """
    Evaluate a challenger result against the active strategy.
    Updates state/comparison.json and returns the new light colour.

    strategy_name: name of the challenger being evaluated
    active_strategy_name: name of the currently active strategy
    """
    state = load_comparison()
    today = date.today().isoformat()

    challenger_score = composite_score(result)
    active_score = composite_score(active_result)
    beating = challenger_score >= active_score

    entry = state.get(
        strategy_name,
        {
            "light": "RED",
            "score": 0.0,
            "days_beating": 0,
            "orange_since": None,
            "last_updated": None,
        },
    )

    light = entry["light"]

    if beating:
        # Coerce None -> 0: the active strategy is written with days_beating=None
        # each cycle, so a strategy that was active in a prior run can re-enter
        # here as a challenger with the key present-but-None ('.get(k, 0)' won't
        # save us). Without this, 'None + 1' raises TypeError.
        entry["days_beating"] = (entry.get("days_beating") or 0) + 1
    else:
        entry["days_beating"] = 0
        # Reset if challenger falls behind while orange
        if light == "ORANGE":
            light = "RED"
            entry["orange_since"] = None

    # Promotion logic
    if light == "RED" and entry["days_beating"] >= DAYS_RED_TO_ORANGE:
        light = "ORANGE"
        entry["orange_since"] = today

    elif light == "ORANGE" and entry["orange_since"]:
        orange_days = (date.today() - date.fromisoformat(entry["orange_since"])).days
        if orange_days >= DAYS_ORANGE_TO_GREEN:
            light = "GREEN"
            _fire_alert(strategy_name, challenger_score, active_score, active_strategy_name)

    entry["light"] = light
    entry["score"] = round(challenger_score, 4)
    entry["active_score"] = round(active_score, 4)
    entry["last_updated"] = today
    state[strategy_name] = entry

    # Always record the active strategy too
    state[active_strategy_name] = {
        "light": "GREEN",
        "score": round(active_score, 4),
        "days_beating": None,
        "orange_since": None,
        "last_updated": today,
        "is_active": True,
    }

    save_comparison(state)
    return light


def _fire_alert(
    challenger: str,
    challenger_score: float,
    active_score: float,
    active: str,
) -> None:
    """Write a human-review alert to state/alerts.jsonl."""
    STATE_DIR.mkdir(exist_ok=True)
    alert = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": "STRATEGY_PROMOTION",
        "message": (
            f"Challenger '{challenger}' has reached GREEN "
            f"(score {challenger_score:.3f} vs active '{active}' score {active_score:.3f}). "
            f"Human review required before switching."
        ),
        "challenger": challenger,
        "active": active,
        "challenger_score": round(challenger_score, 4),
        "active_score": round(active_score, 4),
        "action_required": "Review and manually update state/strategy.yaml if switching.",
    }
    with open(ALERTS_FILE, "a") as f:
        f.write(json.dumps(alert) + "\n")

    # Also attempt a Windows desktop notification (non-fatal if unavailable)
    try:
        from win10toast import ToastNotifier  # type: ignore

        ToastNotifier().show_toast(
            "Trading Agent Alert",
            f"Challenger '{challenger}' ready for promotion review.",
            duration=10,
            threaded=True,
        )
    except Exception:
        pass


def traffic_light_summary() -> str:
    """Return a formatted table of current traffic light states."""
    state = load_comparison()
    if not state:
        return "No comparison data yet."
    lines = [f"{'Strategy':<25} {'Light':<8} {'Score':>6} {'Active Score':>12} {'Days':>6}"]
    lines.append("-" * 62)
    for name, entry in sorted(state.items()):
        light = entry.get("light", "?")
        score = entry.get("score", 0)
        active_score = entry.get("active_score", score)
        days = entry.get("days_beating", "-")
        marker = " <-- ACTIVE" if entry.get("is_active") else ""
        lines.append(
            f"{name:<25} {light:<8} {score:>6.3f} {active_score:>12.3f} {str(days):>6}{marker}"
        )
    return "\n".join(lines)
