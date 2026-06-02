# Related work & novelty positioning

Searched 2026-06-02 (general web + arXiv q-fin + SSRN). Updated as the lit
review deepens. **Do not write "first" anywhere** — see the Krause cluster below.
Frame novelty as "to our knowledge, the first to *jointly* [intraday +
full-corpus ML classification + endogenous-timing control]".

## The closest prior work (must cite, must differentiate)

**David Krause (SSRN, 2025) — the direct competitors.** An active author with
several working papers on Trump and crypto:
- *Trump-Era Cryptocurrency Policy Events and Bitcoin Returns: An Event Study
  Analysis* — daily event study, ~hand-curated policy events, mean 3-day CAR
  2.22% (p=0.038), 78.6% positive.
- *Trump, Tokens, and Tailwinds: Digital Asset Reactions to Presidential Crypto
  Advocacy* — high-frequency event study of Trump-family crypto advocacy vs S&P.
- *Tariffs, Tokens, and Turmoil: Market Fallout from Trump's Policy Uncertainty*
  — Apr 2024–Apr 7 2025, cross-asset (equities/crypto/gold/bonds).

How we differ (the niche):
1. **Resolution.** Krause uses daily data / multi-day CAR windows. Our effect is
   a **1–4h intraday** volatility phenomenon invisible at daily resolution.
2. **Event construction.** Krause hand-curates discrete policy events; we
   **systematically classify the entire 33k-post corpus** with a reproducible,
   text-only ML pipeline (FinBERT + LLM stance + embeddings). No event cherry-
   picking.
3. **Second moment + the clustering caveat.** We focus on realized volatility
   and show the **24h effect is largely volatility clustering** while only the
   1–4h effect survives a trailing-vol-matched null — a rigor result absent from
   the daily CAR literature.
4. **Endogenous-timing control.** We address "he posts *because* markets are
   already moving" with a vol-quintile-matched null + trailing-vol regression
   control. This is our methodological core.

## Trump-tweets-and-equities literature (mature; cite as background)

- **Nishimura & Sun (2021), *J. Financial Research*** — Trump tweets' sentiment,
  stock-market volatility and jumps; second-moment response significant in the
  later sample.
- **JPMorgan "Volfefe Index" (2019)** — practitioner index of Trump-tweet-driven
  Treasury vol; Klaus & Koser (2020) test its predictive value for European
  equities.
- US–China tweet / trade-conflict volatility studies (G5 + China).

Gap: this literature is **Twitter + equities/bonds, pre-2021**. We are **Truth
Social + crypto, 2022–2026**, the second-term tariff-war regime — a different
platform, asset class, and policy regime.

## Crypto-sentiment literature (background)

- Musk-tweet → crypto abnormal-return studies (single-author signalling).
- Twitter-sentiment → BTC/ETH/LTC/XRP high-frequency liquidity/vol (2017–2021).
- 2025–26 reviews: sentiment effects on crypto are nonlinear, regime-dependent.

Gap: aggregate/retail Twitter sentiment, not a **single high-authority actor
whose posts can precede the very policy they react to** (the directive case).

## Documented episodes (report as dated fact, NOT as proven manipulation)

- **2025-03-03** "Strategic National Crypto Reserve" Truth Social post → BTC
  +~8% to >$91k.
- **2025-04-09** "THIS IS A GREAT TIME TO BUY!!! DJT" ~4h before the 90-day
  tariff-pause announcement; markets rallied sharply; Sen. Schiff and others
  publicly called for insider-trading / manipulation investigations.
- **2025-10-10** "100% tariffs on China" post → BTC −12.4% in ~2h; ~$19B
  liquidations (largest single-day at the time).

Framing rule: the paper studies the *informational content and abnormal
reactions* around these posts and reports the allegations with citations and
dates. It does **not** conclude manipulation. Neutral language throughout
("official communications", "abnormal returns/volatility around posts").

## Sources
- Nishimura, Y. (2021) J. Financial Research 44(3):497-512 — https://ideas.repec.org/a/bla/jfnres/v44y2021i3p497-512.html
- Volfefe Index — https://en.wikipedia.org/wiki/Volfefe_index
- Krause, *Trump-Era Cryptocurrency Policy Events* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5863983
- Krause, *Trump, Tokens, and Tailwinds* — https://papers.ssrn.com/sol3/Delivery.cfm/5241126.pdf?abstractid=5241126
- Krause, *Tariffs, Tokens, and Turmoil* — https://papers.ssrn.com/sol3/Delivery.cfm/5210267.pdf?abstractid=5210267
- Farzulla (2026), *Same Returns, Different Risks* — https://arxiv.org/pdf/2602.07046
- MDPI review, *From Tweets to Trades* (2025) — https://www.mdpi.com/2227-7072/13/2/87
- Schiff/insider-trading coverage of Apr 9 post — Fortune — https://fortune.com/crypto/2025/04/09/crypto-prices-rise-trump-tariff-pause-announcement/
- Oct 10 China-tariff crypto crash — CNN — https://www.cnn.com/2025/10/13/business/crypto-bitcoin-price-drop-trump-tariffs
