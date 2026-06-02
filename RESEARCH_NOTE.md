# Regime-Aware Directional Bias in Cryptocurrency Mean-Reversion Strategies

### A walk-forward study on BTC/USDT, and a rigorous negative result

*Working research note — solo project. Last updated 2026-06-02.*
*All figures are sourced to commits, logs, and scripts in this repository (see §10 Reproducibility).*

---

## 1. Abstract

We ask whether a portfolio of technical trading strategies — mean-reversion, trend-following,
and multi-timeframe confluence — can achieve a **robust, cost-adjusted edge** on hourly BTC/USDT,
and whether a **regime-aware directional bias** (only go long in bull regimes, only short in bear
regimes) can rescue strategies that fail unconstrained.

Across **eleven strategies**, a 5-year walk-forward backtest with realistic costs, block-bootstrap
confidence intervals, and a held-out out-of-sample (OOS) period, the answer is **no**. The single
most promising signal — an ADX-gated Bollinger-band mean-reversion strategy (`regime_bb`) run with
directional bias — produced a headline OOS Sharpe of **+0.66** that does **not survive adversarial
validation**: it rests on a single ~6-trade 2024 bull fold, breaks one grid-step away in parameter
space, collapses to ~0 when given more held-out data, and a 864-combination re-optimisation
*against the directional metric itself* overfits the training window (the in-sample champion is the
worst performer OOS). A separately strong-looking candidate, `bollinger` (reflect Sharpe **+2.55**),
is shown to be a **pooling artifact** of ~13 sparse trades whose wins happened to land in the test
window — zero of ten disjoint 6-month windows are statistically significant.

The contribution is therefore methodological: (i) a reusable **adversarial validation harness**
(disjoint-window stability, parameter perturbation, split/threshold sensitivity, and
re-optimisation-then-OOS) that distinguishes real edges from artifacts; (ii) a documented set of
**failure modes** specific to low-frequency crypto strategies — sparse-trade Sharpe inflation, a
gameable composite promotion score, single-fold "wins," and overfitting under re-optimisation; and
(iii) an honest **negative result** that should prevent capital being allocated to noise.

---

## 2. Motivation

The project began (commit `e41659a`, 2026-05-24) as a self-improving paper-trading agent: a
walk-forward backtester, a library of candidate strategies, and a "traffic light" promotion system
that flags a challenger for human review only after it beats the active strategy for a sustained
period. The guiding question was practical, not academic: **is there a strategy worth trading?**

As strategy after strategy failed unconstrained (§5), a specific hypothesis emerged:

> **H1.** Technical strategies fail on BTC because they fight the macro regime — mean-reversion
> shorts get run over in bull markets, longs get run over in bear markets. If we *constrain*
> each strategy to trade only with the prevailing regime (long-only in bull, short-only in bear),
> the cost-adjusted edge should improve.

This note documents the test of H1 and its adversarial validation.

---

## 3. Data

- **Source:** `crypto-lake-rs` parquet store (DuckDB, hive-partitioned by day), symbol **BTCUSDT**.
- **Resolution:** 1-minute bars resampled to **1-hour** for all backtests (the strategy/optimiser/
  reflect convention). Daily and 4-hour series are derived on demand for regime and ADX gates.
- **Coverage:** clean *backfill* data spans 2020 → ~2026-04-29. More recent days exist only as
  live 1-second data with partial (corrupt-tail) files, so all backtests use `backfill_only=True`.
- **Multi-asset:** ETH/USDT and SOL/USDT have no pre-2026 history in the lake; the multi-asset
  test (§5.4) therefore used Yahoo Finance hourly bars.

**Transaction costs (applied to every round trip):** 0.1% taker fee × 2 sides + 2 bps slippage × 2
sides = **~0.24% per round trip**. This is the single most important number in the study: most
strategies that look profitable gross are unprofitable net of this drag.

---

## 4. Methodology

- **Walk-forward split.** Each backtest fits parameters on the first 80% of the window and trades
  only on the held-out final 20%. No lookahead: the strategy sees bars only up to the current bar.
- **Block-bootstrap Sharpe CI.** 1000 resamples, block size 20 bars, 95% interval. We treat a
  result as *significant* only when the **lower CI bound > 0** (tagged `[+]`); a CI spanning zero
  (`[~]`) is noise regardless of the point estimate. This distinction does almost all the work in §6.
- **Regime detection.** Each daily bar is labelled by its trailing **90-day return**:
  > +10% → **bull**, < −10% → **bear**, otherwise **ranging**. Backward-looking, hence causal/safe
  for live use.
- **Regime folds.** For regime-aware walk-forward, fold boundaries are placed at regime transitions
  (blocks < 30 days merged into neighbours), so each fold carries a dominant regime label.
- **Directional bias (the H1 mechanism).** `run_backtest(direction=...)` filters signals *before*
  entry: in `long` mode all short signals are suppressed, in `short` mode all longs are suppressed.
  The walk-forward maps **bull→long-only, bear→short-only, ranging→both** (commit `ae3b6b6`).
- **Promotion (traffic light).** A composite score
  `Sharpe×0.4 + win_rate×0.3 + drawdown_score×0.3` ranks challengers; RED→ORANGE after 7 cycles
  beating the active strategy, ORANGE→GREEN after 14 calendar days. Only a human switches the
  active strategy. **Note:** §7 shows this composite is gameable by sparse, high-win-rate strategies.

---

## 5. Strategy library and unconstrained results

Eleven strategies were implemented and optimised by grid search. Unconstrained (long/short as each
strategy sees fit), **none achieved a significant positive Sharpe** on the 5-year walk-forward.

| Strategy | Type | Representative result (unconstrained) | Source |
|---|---|---|---|
| `markov_regime` | 3-state regime chain on 20-day returns | initial active strategy | `e41659a` |
| `rsi_meanrev` | RSI dip-buy | catastrophic on 1h (over-trades) | `8b49c7c` |
| `ema_crossover` | EMA trend-follow + macro filter | negative net of costs | `2558972` |
| `mtf_confluence` | 4-layer daily/4h/1h/VWAP | **216 combos, all negative Sharpe** | `57216c1` |
| `mtf_ls` | long/short MTF | deeply negative, hundreds of trades | `d8fd85a` |
| `breakout` | turtle N-day channel | Sharpe **−0.255** [−2.46, +1.59] — *first CI to span zero* | `7e55885` |
| `daily_swing` | daily-bar RSI/MACD swing | low frequency, weak timing | `7e55885` |
| `bollinger` | BB touch + EMA-slope filter | in-sample OOS Sharpe **1.909** [0.33, 3.35] (see §7) | `f2f94f4` |
| `mtf_bb_vol` | BB + relative-volume + MTF | mixed, mostly negative | `633fbf9` |
| `regime_bb` | **ADX-gated** BB mean-reversion | 864 combos; ADX<20 → 88% train / 73% OOS WR but only 11–18 trades (inconclusive) | `bab47d7` |
| `ensemble` | majority vote across the 8 base strategies | vote≥4/5 → 33–34% WR | `bab47d7` |

**Three diagnostic findings from this phase:**

1. **`breakout` reaching a CI that merely *spans* zero was the best unconstrained result** — i.e.
   the ceiling of the unconstrained library was "indistinguishable from no edge."
2. **The ensemble does not help.** Combining strategies that share the same regime bias just
   confirms the shared failure mode — majority vote produced 33–34% win rates (`bab47d7`).
3. **The failure is market-wide, not BTC-specific (§5.4).** Running the BTC-optimised `mtf_bb_vol`
   on other assets: **ETH Sharpe −2.58, SOL −2.11, BTC −1.26** (Dec 2024 – May 2026). The strategies
   are not mistuned to BTC; the edge is absent everywhere.

### 5.4 The ADX gate: quality vs. starvation

`regime_bb`'s thesis is that BB mean-reversion only works in *ranging* markets, so it gates entries
on 4-hour ADX < threshold (only trade when not trending). Strict gating (ADX<20) lifted the win
rate to 88% in-sample / 73% OOS — but cut the trade count to **11–18 over three years**, far too
few for the bootstrap CI to separate from zero. This "quality vs. starvation" tension recurs
throughout: the cleaner the signal, the sparser the sample, the less we can trust the Sharpe.

---

## 6. The directional-bias experiment (testing H1)

### 6.1 A/B walk-forward (commit `ae3b6b6`)

Same regime folds (2021-05 → 2026-04; 6 bull, 2 bear, 2 ranging), run twice — once unconstrained,
once with directional bias — to isolate the effect of the bias from the folding itself.

| Strategy | Avg Sharpe (baseline) | Avg Sharpe (directional) | Δ |
|---|---|---|---|
| `regime_bb` | −0.24 | **+0.61** | **+0.85** |
| `breakout` | −0.65 | +0.08 | +0.73 |
| `mtf_bb_vol` | −1.10 | −0.27 | +0.83 |
| `ema_crossover` | −1.48 | −0.66 | +0.82 |
| `ensemble` | −0.97 | **−1.09** | **−0.12** |
| *(avg across 9/10 strategies)* | | | **+0.57 Sharpe, +8.3% return** |

Directional bias helped **9 of 10** strategies. `regime_bb` became the only strategy with a positive
average. `ensemble` was the lone casualty — its vote threshold was never met on the short side in
bear folds, so the filter simply starved it. **On its face, H1 looked confirmed.**

> ⚠️ **Caveat recorded at the time:** every individual fold CI still spanned zero. The +0.61 was an
> *average of noisy folds*, not a significant per-fold edge.

### 6.2 Out-of-sample validation (commit `a55a07f`)

Clean train/OOS split at **2024-05-25** (nothing after touched during fitting). Regime detection
run on full history so OOS-boundary bars get valid 90-day lookbacks. Each OOS regime block tested
with its directional constraint.

| OOS fold | Regime | Dir | Sharpe | 95% CI | Return | Trades |
|---|---|---|---|---|---|---|
| 2024-05 → 2024-10 | bull | long | **+3.26** | **[+1.82, +4.53]** ✅ | +5.9% | 6 |
| 2024-10 → 2025-05 | bull | long | +0.34 | [−1.60, +5.16] | +1.8% | 13 |
| 2025-05 → 2025-11 | bull | long | −0.95 | [−2.53, +3.27] | −5.7% | 4 |
| 2025-11 → 2026-04 | bear | short | 0.00 | — (0 trades) | 0.0% | 0 |
| **Aggregate** | | | **+0.663** | | +0.5% | 23 (91% WR) |

The first fold was the **only statistically significant result the project ever produced** (CI fully
above zero). The bear fold was silent — the ADX gate correctly declined to trade a *trending*
decline, exposing that `regime_bb` is structurally a ranging-market instrument with no bear-market
coverage. **23 trades over two years** was already a thin basis for an aggregate claim.

---

## 7. Adversarial validation (the decisive phase)

Four independent stress tests were run (three in parallel, plus a confirmatory re-optimisation).
Every one cut against the candidates.

### 7.1 `bollinger`'s +2.55 is a pooling artifact
The reflect cycle scored `bollinger` at Sharpe **+2.55**, CI [+0.71, +4.01], 92% win rate — the
strongest-looking number on the traffic light. Tested across **10 disjoint 6-month windows**:
**0 were significant** (no window's CI low > 0). The strategy fires only 0–3 trades per window (two
windows: zero trades). The high Sharpes (+4.45, +4.33) each rest on **1–2 trades** with CI low pinned
at exactly 0.00 → tagged `[~]`, never `[+]`. The wins cluster in 2021 and 2025; the 2025 windows
**overlap the reflect test period**, so the headline simply pools ~13 sparse lucky trades. The 92%
win rate decomposes to 67% (3 trades) in 2023-H1 and 0% (1 trade) in 2022-H2. **Verdict: overfit /
do not deploy.**

### 7.2 `regime_bb` directional is a knife-edge (parameter perturbation)
Perturbing the OOS-winning params one grid-step at a time: all 7 perturbations kept avg Sharpe > 0,
but only **4/7 kept the load-bearing fold-1 CI low > 0**. It broke on two axes:
- `bb_std` 2.0→2.5: fold-1 CI low → 0.000 (trade count thinned 23→16).
- `adx_threshold` 20→25: fold-1 +3.26 → +0.41, CI low **−2.0**; 20→30: fold-1 → +0.03, CI low −2.0.

Worse, **loosening the ADX gate *raises* the aggregate Sharpe (+0.89) while destroying the fold-1
edge** — the +0.66 aggregate actively *masks* the fragility. **Verdict: fragile.**

### 7.3 `regime_bb` directional is split-sensitive
Varying analysis choices, one at a time:
- **Train cutoff** (held-out length): 2024-01-01 → avg Sharpe **−0.06** (edge gone); 2024-05-25 →
  +0.66; 2024-09-01 → +0.70. **Monotonic: more held-out data → worse.** Textbook overfit signature.
- **Regime thresholds** (±5/10/15%): all positive (+1.46 / +0.66 / +1.84) — robust on *this* axis,
  and the base 0.10 is the *weakest*, so the threshold choice did not flatter the result.

Positive folds never exceed ~50% in any variation. **Verdict: fragile** (split-dependent, not
threshold-dependent).

### 7.4 Re-optimising for the directional metric overfits (864 combos → OOS)
We re-ran the full 864-combination grid on the 2021–2024 training window, ranking by the directional
fold metric itself (not single-split Sharpe). The in-sample champion looked better than the original
(avg Sharpe **+1.85**, 6/7 positive folds, +5.1% return) — but it used `bb_std=2.5` and
`adx_threshold=25`, **exactly the two params §7.2 showed kill the OOS edge.** Tested OOS:

| Param set | In-sample | **OOS avg Sharpe** | OOS sig folds | fold-1 CI low |
|---|---|---|---|---|
| ORIGINAL (hand-picked) | — | **+0.663** | 1 | **+1.82** ✅ |
| RE-OPT champion (`bbs2.5/adxt25`) | +1.85 | **+0.595** ↓ | **0** | **−2.03** ✗ |
| RE-OPT #2 | — | +0.619 | 1 | +1.82 |
| RE-OPT #3 | — | +0.692 | 0 | +0.00 ✗ |

**The param set that won biggest in-sample is the worst out-of-sample and loses the only significant
fold.** No re-optimised candidate beats the original on Sharpe *and* keeps a significant fold. Every
candidate earns ~0–1% return. **Verdict: re-optimisation overfits the training window.**

---

## 8. Discussion

**Why these strategies fail, and why the failures are easy to mistake for success:**

1. **Sparse-trade Sharpe inflation.** A strategy firing 1–3 trades per window can post a spectacular
   Sharpe and 100% win rate purely by chance; the bootstrap CI correctly refuses to call it
   significant, but a *point-estimate* leaderboard (or a composite score) will rank it top.
2. **The composite promotion score is gameable.** `Sharpe×0.4 + win_rate×0.3 + dd×0.3` rewarded
   `bollinger` (sparse, 92% WR, tiny drawdown) far above its true reliability. Win-rate and
   drawdown terms reward exactly the low-frequency strategies whose Sharpe is least trustworthy.
3. **Single-fold wins masquerade as edges.** `regime_bb`'s entire OOS result is one 2024 bull fold.
   Aggregating across folds hid that the other three were noise or silent.
4. **Re-optimisation manufactures overfit.** Searching 864 combinations against the very metric you
   report guarantees you find the params that best fit *this* history — which then underperform OOS.
5. **Aggregate metrics can move opposite to the real edge.** Loosening the ADX gate raised average
   Sharpe while destroying the only significant fold — a warning that the headline statistic and the
   real signal can point in opposite directions.

The directional bias (H1) is *real but small and non-robust*: it genuinely reduces the damage of
trading against the regime (9/10 strategies improved in-sample), but it cannot manufacture an edge
where none exists — it shifts a −0.6 Sharpe to a fragile, ~0%-return +0.6 that does not generalise.

---

## 9. Conclusion

**H1 is rejected in its strong form.** Regime-aware directional bias improves cost-adjusted
performance on average but does not produce a robust, profitable, statistically significant edge in
any strategy in this library on hourly BTC/USDT. There is, at present, **no strategy worth
promoting to live capital.**

This is a useful negative result. The system is now correctly instrumented to keep searching
honestly:
- the live paper-trading loop runs the configured strategy and all challengers (long/short, with
  stop-loss and an optional causal directional gate);
- the promotion scoring no longer crashes when a strategy is both active and challenger;
- a Streamlit dashboard visualises equity curves, regime-folded Sharpe, and the traffic light;
- and the **adversarial validation harness** (§7) is the reusable contribution: *any* future
  candidate must pass disjoint-window stability, parameter perturbation, split sensitivity, and
  re-optimisation-then-OOS before it is trusted.

**The clearest single lesson:** on low-frequency crypto strategies, a high point-estimate Sharpe or
win rate is not evidence of an edge. Only a lower CI bound above zero that *survives perturbation
and additional held-out data* is — and nothing here cleared that bar.

---

## 10. Reproducibility

| Artifact | Path |
|---|---|
| Backtester (walk-forward, costs, bootstrap CI) | `local_system/backtester.py` |
| Strategy registry + grids | `local_system/strategies/registry.py` |
| Regime-fold + directional walk-forward | `local_system/cli/walkforward.py` (`--regime-folds --directional`) |
| OOS directional validation | `_oos_regime_bb_directional.py` |
| Directional re-optimisation (864 combos) | `_optimize_regime_bb_directional.py` |
| Adversarial validation scripts | `_val_bollinger.py`, `_val_regimebb_perturb.py`, `_val_regimebb_altsplit.py`, `_val_reopt_oos.py` |
| Optimiser CSVs / walk-forward logs | `state/optimize_*.csv`, `state/walkforward_*.log` |
| Dashboard | `dashboard.py` (`uv run streamlit run dashboard.py`) |

Key commits: `e41659a` (system), `ae3b6b6` (directional bias + A/B), `a55a07f` (OOS validation),
`8836b2d` (live-path fix + directional optimiser).

Run a backtest cycle: `LAKE_ROOT=… uv run python -m local_system.cli.reflect --years 5`
Run the directional A/B: `… walkforward --regime-folds --from 2021-05-25 --to 2026-05-24 [--directional]`

---

## 11. Limitations & future work

**Limitations.** Single asset with long history (BTC); 1-hour resolution only; the OOS window
(2024–2026) is itself regime-skewed (mostly bull); the bear case is essentially untested because the
one bear fold produced zero trades; trade counts are small throughout.

**Future directions (not yet tested):**
- **Structurally different families** — higher-timeframe (4h/daily) trend-following, volatility
  targeting, or carry — rather than further mean-reversion variants that share the failure mode.
- **Live-data hardening** — make the lake loader resilient to partial live files so forward
  paper-tracking accumulates genuine out-of-sample evidence in real time (currently pinned to the
  last clean backfill bar).
- **A non-gameable promotion metric** — penalise sparse-trade Sharpe (e.g. require a minimum trade
  count or a CI-low threshold) so the traffic light cannot promote artifacts like §7.1.
- **Bear-regime instrument** — the directional approach has no short-side edge because the ADX gate
  silences it in trending bears; a dedicated trending-bear strategy would be needed for symmetry.
