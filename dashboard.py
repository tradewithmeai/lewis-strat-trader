"""
Strategy Research Dashboard
Run with: uv run streamlit run dashboard.py
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "state"
LAKE_ROOT = os.environ.get("LAKE_ROOT", "D:/Documents/11Projects/crypto-lake-rs/data/parquet")

st.set_page_config(
    page_title="Strategy Dashboard",
    page_icon="📈",
    layout="wide",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

LIGHT_COLOURS = {"GREEN": "#00c853", "ORANGE": "#ff6d00", "RED": "#d50000"}
REGIME_COLOURS = {
    "bull": "rgba(0,200,83,0.12)",
    "bear": "rgba(213,0,0,0.12)",
    "ranging": "rgba(255,193,7,0.10)",
}
STRATEGY_COLOURS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


@st.cache_data(ttl=30)
def load_comparison() -> dict:
    p = STATE_DIR / "comparison.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


@st.cache_data(ttl=30)
def load_progress() -> dict:
    p = ROOT / "docs" / "PAPER" / "progress.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data(ttl=300)
def load_bars_cached(symbol: str, start: date, end: date) -> pd.DataFrame:
    os.environ["LAKE_ROOT"] = LAKE_ROOT
    from local_system.lake_adapter import load_bars, resample_ohlcv

    df_1m = load_bars(symbol, start, end, backfill_only=True)
    return resample_ohlcv(df_1m, "1h")


@st.cache_data(ttl=300)
def run_backtest_cached(
    strategy_name: str, params_json: str, start: date, end: date, symbol: str, directional: bool
):
    import json as _json
    from local_system.backtester import run_backtest
    from local_system.strategies.registry import get_strategy

    params = _json.loads(params_json)
    df = load_bars_cached(symbol, start, end)
    strat = get_strategy(strategy_name, params)
    return run_backtest(df, strat, symbol=symbol)


@st.cache_data(ttl=300)
def run_regime_folds_cached(
    strategy_name: str, params_json: str, start: date, end: date, symbol: str, directional: bool
):
    import json as _json
    from local_system.backtester import run_backtest
    from local_system.cli.walkforward import _regime_fold_boundaries, _run_folds
    from local_system.strategies.registry import get_strategy

    params = _json.loads(params_json)
    df = load_bars_cached(symbol, start, end)
    strat = get_strategy(strategy_name, params)
    folds = _regime_fold_boundaries(df)
    return _run_folds(df, strat, symbol=symbol, folds=folds, directional=directional)


def detect_regimes_on_df(df: pd.DataFrame) -> list[tuple]:
    """Return (start_ts, end_ts, label) blocks for regime shading."""
    from local_system.cli.walkforward import _detect_regimes

    daily = df["close"].resample("1D").last().dropna()
    regime = _detect_regimes(daily)
    blocks = []
    cur_label, cur_start = None, None
    for ts, lbl in regime.items():
        if lbl != cur_label:
            if cur_label is not None:
                blocks.append((cur_start, ts, cur_label))
            cur_label, cur_start = lbl, ts
    if cur_label is not None:
        blocks.append((cur_start, regime.index[-1], cur_label))
    return blocks


def strategy_defaults(name: str) -> dict:
    from local_system.strategies.registry import REGISTRY

    entry = REGISTRY.get(name, {})
    grid = entry.get("grid", {})
    return {k: v[0] if isinstance(v, list) else v for k, v in grid.items()}


def available_strategies() -> list[str]:
    from local_system.strategies.registry import REGISTRY

    return sorted(REGISTRY.keys())


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("Strategy Dashboard")

tab_choice = st.sidebar.radio(
    "View",
    ["Research Progress", "Traffic Light", "Equity Curves", "Walk-forward Folds", "Trade Log"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.subheader("Settings")

end_default = date.today() - timedelta(days=1)
start_default = end_default - timedelta(days=5 * 365)

col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("From", value=start_default)
end_date = col2.date_input("To", value=end_default)

symbol = st.sidebar.text_input("Symbol", value="BTCUSDT")

strategies = available_strategies()
selected = st.sidebar.multiselect(
    "Strategies",
    options=strategies,
    default=["regime_bb", "bollinger", "breakout"],
)

directional = st.sidebar.checkbox(
    "Directional bias (bull=long-only, bear=short-only)",
    value=True,
    help="Applies directional constraint per regime fold. Only affects Walk-forward Folds view.",
)

st.sidebar.markdown("---")
st.sidebar.caption(f"LAKE_ROOT: `{LAKE_ROOT}`")

# ── Tab: Traffic Light ────────────────────────────────────────────────────────

if tab_choice == "Research Progress":
    st.title("Research Progress — Undergrad → Master's → PhD")
    prog = load_progress()
    if not prog:
        st.warning("docs/PAPER/progress.json not found.")
    else:
        TIER_ORDER = ["undergrad", "masters", "phd"]
        TIER_COLOUR = {"undergrad": "#1f77b4", "masters": "#9467bd", "phd": "#2ca02c"}
        STATUS_W = {"done": 1.0, "active": 0.5, "todo": 0.0}
        tiers = prog.get("tiers", {})
        st.caption(f"Last updated: {prog.get('updated', '?')} · updated nightly by the /signoff routine")

        # ── per-tier completion bars ─────────────────────────────────────────
        pct = {}
        for t in TIER_ORDER:
            ms = tiers.get(t, {}).get("milestones", [])
            pct[t] = (sum(STATUS_W.get(m["status"], 0) for m in ms) / len(ms) * 100) if ms else 0
        fig = go.Figure()
        for t in TIER_ORDER:
            fig.add_trace(go.Bar(
                y=[tiers.get(t, {}).get("title", t)], x=[pct[t]], orientation="h",
                marker_color=TIER_COLOUR[t], text=f"{pct[t]:.0f}%", textposition="auto",
                hovertemplate=f"{pct[t]:.0f}%<extra></extra>",
            ))
        fig.update_layout(
            title="Tier completion (done=1, active=0.5)", xaxis_range=[0, 100],
            xaxis_title="% complete", showlegend=False, height=240,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── cumulative milestones completed over time ────────────────────────
        rows = []
        for t in TIER_ORDER:
            for m in tiers.get(t, {}).get("milestones", []):
                if m["status"] == "done" and m.get("date"):
                    rows.append({"tier": t, "date": m["date"]})
        if rows:
            tl = pd.DataFrame(rows)
            tl["date"] = pd.to_datetime(tl["date"])
            figc = go.Figure()
            for t in TIER_ORDER:
                sub = tl[tl.tier == t].sort_values("date")
                if len(sub):
                    cum = sub.groupby("date").size().cumsum()
                    figc.add_trace(go.Scatter(
                        x=cum.index, y=cum.values, mode="lines+markers", name=t,
                        line=dict(color=TIER_COLOUR[t], shape="hv"),
                    ))
            figc.update_layout(
                title="Milestones completed over time", height=300,
                xaxis_title="date", yaxis_title="cumulative milestones",
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(figc, use_container_width=True)

        # ── milestone tables per tier ────────────────────────────────────────
        ICON = {"done": "✅", "active": "🟡", "todo": "⬜"}
        for t in TIER_ORDER:
            tier = tiers.get(t, {})
            st.subheader(f"{tier.get('title', t)} — {pct[t]:.0f}%")
            tbl = pd.DataFrame([
                {"": ICON.get(m["status"], "?"), "Milestone": m["name"],
                 "Done": m.get("date") or ""}
                for m in tier.get("milestones", [])
            ])
            st.dataframe(tbl, use_container_width=True, hide_index=True)

elif tab_choice == "Traffic Light":
    st.title("Traffic Light — Challenger Scores")
    comp = load_comparison()

    if not comp:
        st.warning("No comparison.json found. Run a reflect cycle first.")
    else:
        rows = []
        for name, info in sorted(comp.items()):
            is_active = info.get("is_active", False)
            light = info.get("light", "RED")
            score = info.get("score", 0.0)
            active_score = info.get("active_score", None)
            days = info.get("days_beating", 0) or 0
            orange_since = info.get("orange_since", "—") or "—"
            updated = info.get("last_updated", "—")
            rows.append(
                {
                    "Strategy": ("⭐ " if is_active else "") + name,
                    "Light": light,
                    "Score": round(score, 4),
                    "Active Score": round(active_score, 4) if active_score else "—",
                    "Days Beating": days,
                    "Orange Since": orange_since,
                    "Updated": updated,
                }
            )

        df_tl = pd.DataFrame(rows)

        def colour_light(val):
            c = LIGHT_COLOURS.get(val, "#888")
            return f"background-color: {c}22; color: {c}; font-weight: bold"

        styled = df_tl.style.map(colour_light, subset=["Light"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Score bars")
        fig = go.Figure()
        names = [r["Strategy"] for r in rows]
        scores = [r["Score"] for r in rows]
        lights = [r["Light"] for r in rows]
        bar_colours = [LIGHT_COLOURS.get(l, "#888") for l in lights]
        fig.add_trace(
            go.Bar(
                x=names,
                y=scores,
                marker_color=bar_colours,
                text=[f"{s:.3f}" for s in scores],
                textposition="outside",
            )
        )
        fig.update_layout(height=350, yaxis_title="Score", xaxis_title="", margin=dict(t=20, b=60))
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "Score is a composite of Sharpe, win rate, and max drawdown from the most recent reflect cycle. GREEN = active. A challenger needs 7 days beating active → ORANGE, then 14 days at ORANGE → GREEN."
        )

# ── Tab: Equity Curves ────────────────────────────────────────────────────────

elif tab_choice == "Equity Curves":
    st.title("Equity Curves")

    if not selected:
        st.info("Select at least one strategy in the sidebar.")
    else:
        with st.spinner(
            f"Loading {len(selected)} strategies on {symbol} {start_date} -> {end_date}..."
        ):
            df = load_bars_cached(symbol, start_date, end_date)

        regime_blocks = detect_regimes_on_df(df)

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.35, 0.65],
            vertical_spacing=0.04,
        )

        # BTC price (top panel)
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["close"],
                name="BTC price",
                line=dict(color="#aaa", width=1),
                showlegend=True,
            ),
            row=1,
            col=1,
        )

        # Regime shading on both panels
        for start_ts, end_ts, lbl in regime_blocks:
            colour = REGIME_COLOURS.get(lbl, "rgba(128,128,128,0.08)")
            for row in [1, 2]:
                fig.add_vrect(
                    x0=start_ts,
                    x1=end_ts,
                    fillcolor=colour,
                    opacity=1.0,
                    layer="below",
                    line_width=0,
                    row=row,
                    col=1,
                )

        # Equity curves (bottom panel)
        results_ok = []
        for i, name in enumerate(selected):
            try:
                params = strategy_defaults(name)
                params_json = json.dumps(params)
                result = run_backtest_cached(
                    name, params_json, start_date, end_date, symbol, directional
                )
                colour = STRATEGY_COLOURS[i % len(STRATEGY_COLOURS)]
                eq = result.equity_curve
                fig.add_trace(
                    go.Scatter(
                        x=eq.index,
                        y=eq.values,
                        name=f"{name}  (Sharpe {result.sharpe:+.2f})",
                        line=dict(color=colour, width=1.5),
                    ),
                    row=2,
                    col=1,
                )
                results_ok.append((name, result))
            except Exception as e:
                st.warning(f"{name}: {e}")

        fig.update_layout(
            height=650,
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
            margin=dict(t=60, b=40),
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="BTC Price (USDT)", row=1, col=1)
        fig.update_yaxes(title_text="Equity (1 = start)", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # Legend for regime shading
        cols = st.columns(3)
        for col, (lbl, colour) in zip(
            cols,
            [
                ("Bull (green tint)", "#00c853"),
                ("Bear (red tint)", "#d50000"),
                ("Ranging (yellow tint)", "#ffc107"),
            ],
        ):
            col.markdown(f'<span style="color:{colour}">■</span> {lbl}', unsafe_allow_html=True)

        # Summary table
        if results_ok:
            st.markdown("---")
            st.subheader("Summary")
            rows = []
            for name, r in results_ok:
                rows.append(
                    {
                        "Strategy": name,
                        "Sharpe": round(r.sharpe, 3),
                        "CI low": round(r.sharpe_ci_low, 2),
                        "CI high": round(r.sharpe_ci_high, 2),
                        "Return": f"{r.total_return * 100:+.1f}%",
                        "CAGR": f"{r.cagr * 100:+.1f}%",
                        "Win rate": f"{r.win_rate:.1%}",
                        "Max DD": f"{r.max_drawdown:.1%}",
                        "Trades": r.n_trades,
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Tab: Walk-forward Folds ───────────────────────────────────────────────────

elif tab_choice == "Walk-forward Folds":
    st.title("Walk-forward Regime Folds")
    if directional:
        st.caption(
            "Directional bias ON — bull folds = long-only, bear folds = short-only, ranging = both."
        )
    else:
        st.caption("Directional bias OFF — all folds unconstrained.")

    if not selected:
        st.info("Select at least one strategy in the sidebar.")
    else:
        all_fold_data = {}
        progress = st.progress(0, text="Running folds...")
        for i, name in enumerate(selected):
            try:
                params = strategy_defaults(name)
                params_json = json.dumps(params)
                folds = run_regime_folds_cached(
                    name, params_json, start_date, end_date, symbol, directional
                )
                all_fold_data[name] = folds
            except Exception as e:
                st.warning(f"{name}: {e}")
            progress.progress((i + 1) / len(selected), text=f"Done {name}")
        progress.empty()

        if not all_fold_data:
            st.error("No fold results.")
        else:
            # Determine fold labels from first strategy
            first_folds = next(iter(all_fold_data.values()))
            fold_labels = [
                f"{r.start.strftime('%Y-%m')}→{r.end.strftime('%Y-%m')} [{getattr(r, 'regime', '?')[:3]}]"
                for r in first_folds
            ]
            regime_labels = [getattr(r, "regime", "ranging") for r in first_folds]

            # Sharpe bar chart per fold, grouped by strategy
            fig = go.Figure()
            for i, (name, folds) in enumerate(all_fold_data.items()):
                sharpes = [r.sharpe for r in folds]
                ci_lows = [r.sharpe - r.sharpe_ci_low for r in folds]
                ci_highs = [r.sharpe_ci_high - r.sharpe for r in folds]
                colour = STRATEGY_COLOURS[i % len(STRATEGY_COLOURS)]
                fig.add_trace(
                    go.Bar(
                        name=name,
                        x=fold_labels,
                        y=sharpes,
                        marker_color=colour,
                        error_y=dict(
                            type="data", symmetric=False, array=ci_highs, arrayminus=ci_lows
                        ),
                    )
                )

            # Regime background bands
            for j, (lbl, reg) in enumerate(zip(fold_labels, regime_labels)):
                colour = REGIME_COLOURS.get(reg, "rgba(128,128,128,0.08)")
                fig.add_vrect(
                    x0=j - 0.5,
                    x1=j + 0.5,
                    fillcolor=colour,
                    opacity=1.0,
                    layer="below",
                    line_width=0,
                )

            fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.4)
            fig.update_layout(
                barmode="group",
                height=450,
                yaxis_title="Sharpe",
                legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
                margin=dict(t=60, b=80),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Average Sharpe summary
            st.subheader("Average Sharpe per strategy")
            rows = []
            for name, folds in all_fold_data.items():
                sharpes = [r.sharpe for r in folds]
                returns = [r.total_return for r in folds]
                n_pos = sum(1 for s in sharpes if s > 0)
                rows.append(
                    {
                        "Strategy": name,
                        "Avg Sharpe": round(sum(sharpes) / len(sharpes), 3),
                        "Best fold": round(max(sharpes), 3),
                        "Worst fold": round(min(sharpes), 3),
                        "Positive folds": f"{n_pos}/{len(folds)}",
                        "Avg Return": f"{sum(returns) / len(returns) * 100:+.1f}%",
                    }
                )
            st.dataframe(
                pd.DataFrame(rows).sort_values("Avg Sharpe", ascending=False),
                use_container_width=True,
                hide_index=True,
            )

# ── Tab: Trade Log ────────────────────────────────────────────────────────────

elif tab_choice == "Trade Log":
    st.title("Trade Log")

    if not selected:
        st.info("Select at least one strategy in the sidebar.")
    elif len(selected) > 1:
        st.info("Select a single strategy in the sidebar to view its trade log.")
    else:
        name = selected[0]
        with st.spinner(f"Running backtest for {name}..."):
            try:
                df = load_bars_cached(symbol, start_date, end_date)
                params = strategy_defaults(name)
                params_json = json.dumps(params)
                result = run_backtest_cached(
                    name, params_json, start_date, end_date, symbol, directional
                )
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        st.subheader(f"{name} — {result.n_trades} trades")
        cols = st.columns(4)
        cols[0].metric("Sharpe", f"{result.sharpe:+.2f}")
        cols[1].metric("Return", f"{result.total_return * 100:+.1f}%")
        cols[2].metric("Win rate", f"{result.win_rate:.1%}")
        cols[3].metric("Max DD", f"{result.max_drawdown:.1%}")

        # Price chart with trade markers
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["close"],
                name="Price",
                line=dict(color="#555", width=1),
                showlegend=False,
            )
        )

        entries_long = [(t.entry_time, t.entry_price) for t in result.trades if t.side == "long"]
        entries_short = [(t.entry_time, t.entry_price) for t in result.trades if t.side == "short"]
        exits = [(t.exit_time, t.exit_price, t.pnl_pct > 0) for t in result.trades]

        if entries_long:
            fig.add_trace(
                go.Scatter(
                    x=[e[0] for e in entries_long],
                    y=[e[1] for e in entries_long],
                    mode="markers",
                    name="Long entry",
                    marker=dict(symbol="triangle-up", size=10, color="#00c853"),
                )
            )
        if entries_short:
            fig.add_trace(
                go.Scatter(
                    x=[e[0] for e in entries_short],
                    y=[e[1] for e in entries_short],
                    mode="markers",
                    name="Short entry",
                    marker=dict(symbol="triangle-down", size=10, color="#ff6d00"),
                )
            )
        win_exits = [(e[0], e[1]) for e in exits if e[2]]
        loss_exits = [(e[0], e[1]) for e in exits if not e[2]]
        if win_exits:
            fig.add_trace(
                go.Scatter(
                    x=[e[0] for e in win_exits],
                    y=[e[1] for e in win_exits],
                    mode="markers",
                    name="Exit (win)",
                    marker=dict(symbol="x", size=9, color="#00c853"),
                )
            )
        if loss_exits:
            fig.add_trace(
                go.Scatter(
                    x=[e[0] for e in loss_exits],
                    y=[e[1] for e in loss_exits],
                    mode="markers",
                    name="Exit (loss)",
                    marker=dict(symbol="x", size=9, color="#d50000"),
                )
            )

        fig.update_layout(
            height=420, margin=dict(t=20, b=40), hovermode="x unified", yaxis_title="Price (USDT)"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Trade table
        if result.trades:
            trade_rows = [
                {
                    "Entry": t.entry_time.strftime("%Y-%m-%d %H:%M"),
                    "Exit": t.exit_time.strftime("%Y-%m-%d %H:%M"),
                    "Side": t.side,
                    "Entry price": round(t.entry_price, 2),
                    "Exit price": round(t.exit_price, 2),
                    "PnL %": f"{t.pnl_pct * 100:+.3f}%",
                    "Result": "WIN" if t.pnl_pct > 0 else "LOSS",
                }
                for t in result.trades
            ]
            df_trades = pd.DataFrame(trade_rows)

            def colour_result(val):
                return "color: #00c853" if val == "WIN" else "color: #d50000"

            st.dataframe(
                df_trades.style.map(colour_result, subset=["Result"]),
                use_container_width=True,
                hide_index=True,
            )
