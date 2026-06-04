# Deploying the dashboard as a public site

The build-in-public surface is the existing Streamlit app, `dashboard.py`. It
runs in two modes automatically, decided by whether the price lake is present
(`LAKE_AVAILABLE = Path(LAKE_ROOT).is_dir()`):

- **Local (lake present):** full strategy lab — Research Progress, Traffic Light,
  Equity Curves, Walk-forward Folds, Trade Log.
- **Public (no lake — e.g. a cloud host):** read-only view — Research Progress
  (the hero / landing) + Traffic Light. The three lake-backed tabs are hidden, so
  the app never crashes for want of data. All it needs is files committed to the
  repo (`docs/PAPER/progress.json`; `state/comparison.json` is gitignored, so
  Traffic Light degrades to an explanatory note on the host).

## Run locally
```bash
uv run streamlit run dashboard.py     # opens http://localhost:8501
```

## Deploy free + public — Streamlit Community Cloud (recommended)
No VPS needed; it serves straight from the public GitHub repo.

1. Go to https://share.streamlit.io and sign in **with the GitHub account that
   owns `tradewithmeai/lewis-strat-trader`** (authorise read access).
2. **New app → from existing repo:**
   - Repository: `tradewithmeai/lewis-strat-trader`
   - Branch: `main`
   - Main file path: `dashboard.py`
3. **Advanced settings → Python version: 3.12** (matches the verified stack).
4. Deploy. The platform installs from `requirements.txt` (core deps only — no
   torch/research stack) and serves the **public view** (no `LAKE_ROOT` on the
   host). First build takes a few minutes.
5. You get a public URL like `https://<app-name>.streamlit.app` — that is the
   build-in-public link to share.

Pushes to `main` auto-redeploy. The nightly `/signoff` updates `progress.json`,
so the published timeline refreshes on the next redeploy.

## Human-only steps (I cannot do these — they need your accounts)
1. **Streamlit Community Cloud sign-in** + authorising the repo (step 1).
2. **Deciding the public app name / URL** (step 2/5).
3. If you ever want the lake-backed tabs public too, that needs a host *with* the
   lake synced (the VPS path in `VPS_SETUP.md`) and `LAKE_ROOT` set there — out of
   scope for the free public deploy.

## Notes
- **Do not** set any live-trading env vars on the host. The public app is
  read-only over committed result files and never runs the signal pipeline or
  touches money (see `VPS_SETUP.md` §8).
- `requirements.txt` pins streamlit/plotly/pandas/statsmodels to the verified,
  AppTest-passing versions; bump deliberately and re-test, don't float them.
- Theme lives in `.streamlit/config.toml`.
