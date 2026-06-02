"""
local_system.signals — exogenous signal collectors for the trading agent.

Sub-modules pull data that lives *outside* the OHLCV price lake and may carry
predictive information: futures/derivatives metrics (funding, open interest,
positioning), macro series and cross-asset correlations, and news/social flow.

Design principles (shared across collectors):
- **Event-time timestamps.** Every record is stamped with the UTC time the event
  actually occurred (funding settlement, bar close, article publish), not the
  time we fetched it — so later joins to price bars are strictly no-lookahead.
- **No keys where possible.** Prefer public/free endpoints so the suite can run
  unattended on a VPS. Key-requiring sources are pluggable and optional.
- **Resilient.** Network calls retry with backoff; a single failing source must
  never take down a collection pass.
- **Persisted to state/signals/.** Parquet for time-series, JSONL for event logs.
"""

from pathlib import Path

SIGNALS_DIR = Path(__file__).parent.parent.parent / "state" / "signals"
