"""
Strategy Research Dashboard
Run with: uv run streamlit run dashboard.py
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "state"
LAKE_ROOT = os.environ.get("LAKE_ROOT", "D:/Documents/11Projects/crypto-lake-rs/data/parquet")

# When the price lake is present (local dev) the full strategy lab is shown.
# On a public host (e.g. Streamlit Community Cloud) the lake is absent, so we
# fall into a read-only "public view": the research-progress timeline + the
# challenger traffic-light, which need only files committed to the repo.
LAKE_AVAILABLE = Path(LAKE_ROOT).is_dir()

st.set_page_config(
    page_title="stratbot · live strategy tournament",
    page_icon="🚦",
    layout="wide",
)

# ── solvX shared analytics + SEO tags ─────────────────────────────────────────────
# Streamlit renders client-side and strips inline <script> from st.markdown, so we
# inject into the TOP document from a zero-height component iframe (window.parent).
# Adds the same first-party analytics.js used across all solvx.uk properties, plus a
# canonical + Open Graph tags Googlebot picks up when it renders the page. Idempotent.
components.html(
    """
    <script>
    (function () {
      var d = window.parent.document, h = d.head;
      if (!d.getElementById('solvx-analytics')) {
        var s = d.createElement('script');
        s.id = 'solvx-analytics'; s.src = 'https://solvx.uk/analytics.js'; s.defer = true;
        h.appendChild(s);
      }
      if (!d.querySelector('link[rel="canonical"]')) {
        var c = d.createElement('link'); c.rel = 'canonical';
        c.href = 'https://stratbot.solvx.uk/'; h.appendChild(c);
      }
      if (!d.querySelector('meta[name="description"]')) {
        var md = d.createElement('meta'); md.name = 'description';
        md.content = 'A live, auto-updating quant strategy tournament — walk-forward Sharpe, drawdown and regime folds across challenger strategies. By solvX.';
        h.appendChild(md);
      }
      var og = {
        'og:title': 'StratBot — live strategy tournament',
        'og:description': 'A live quant strategy tournament: walk-forward Sharpe, drawdown and regime folds across challenger strategies.',
        'og:type': 'website', 'og:url': 'https://stratbot.solvx.uk/', 'og:site_name': 'solvX'
      };
      Object.keys(og).forEach(function (k) {
        if (!d.querySelector('meta[property="' + k + '"]')) {
          var m = d.createElement('meta'); m.setAttribute('property', k);
          m.setAttribute('content', og[k]); h.appendChild(m);
        }
      });
    })();
    </script>
    """,
    height=0,
)

# ── Theme (quant terminal: charcoal + purple accent + traffic-light greens) ─────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
    :root{
      --bg:#0e0b16; --panel:#171221; --edge:#2a2138;
      --ink:#ece9f5; --muted:#9b93b5;
      --purple:#a855f7; --purple-dim:#6d28d9;
      --green:#00c853; --orange:#ff6d00; --red:#d50000;
    }
    .stApp{ background:
        radial-gradient(1100px 520px at 82% -12%, #241640 0%, rgba(36,22,64,0) 60%),
        var(--bg); }
    html, body, [class*="css"], .stMarkdown, p, span, label, div, input, textarea{
        font-family:'IBM Plex Mono', ui-monospace, monospace; }
    h1, h2, h3, h4{ font-family:'Archivo', sans-serif !important; letter-spacing:-0.02em; }
    h1{ font-weight:800 !important; }
    /* cleaner public face */
    #MainMenu{ visibility:hidden; }
    header[data-testid="stHeader"]{ background:transparent; }
    footer{ visibility:hidden; }
    a{ color:var(--purple) !important; }
    [data-testid="stSidebar"]{ background:var(--panel); border-right:1px solid var(--edge); }
    /* selected radio + interactive accents in purple */
    [data-testid="stSidebar"] .stRadio [aria-checked="true"] p{ color:var(--purple) !important; font-weight:600; }
    .stExpander{ border:1px solid var(--edge) !important; border-radius:10px; background:rgba(23,18,33,0.6); }
    [data-testid="stMetricValue"]{ font-family:'IBM Plex Mono', monospace; }
    /* the discreet admin trigger button in the sidebar footer */
    [data-testid="stSidebar"] .stButton button{ background:transparent; border:1px solid var(--edge); color:var(--muted); }
    [data-testid="stSidebar"] .stButton button:hover{ border-color:var(--purple); color:var(--purple); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Access control: public by default; hidden 7-click + password unlocks admin ──
import hmac

ADMIN_PASSWORD = os.environ.get("DASHBOARD_ADMIN_PASSWORD", "")
st.session_state.setdefault("admin", False)
st.session_state.setdefault("_clicks", 0)


def _check_pw(pw: str) -> bool:
    """Constant-time check; never unlocks if the env password is unset."""
    return bool(ADMIN_PASSWORD) and hmac.compare_digest(pw, ADMIN_PASSWORD)


def render_admin_gate() -> None:
    """Sidebar footer: a discreet 7-click trigger that reveals a password field."""
    st.sidebar.markdown("---")
    if st.session_state.admin:
        st.sidebar.caption("🔓 admin view")
        if st.sidebar.button("exit admin", use_container_width=True):
            st.session_state.admin = False
            st.session_state._clicks = 0
            st.rerun()
        return
    foot, trigger = st.sidebar.columns([5, 1])
    foot.caption("stratbot · live tournament")
    if trigger.button("·", key="_secret"):
        st.session_state._clicks += 1
    if st.session_state._clicks >= 7:
        pw = st.sidebar.text_input(
            "access", type="password", label_visibility="collapsed", placeholder="password"
        )
        if pw:
            if _check_pw(pw):
                st.session_state.admin = True
                st.session_state._clicks = 0
                st.rerun()
            else:
                st.sidebar.error("incorrect")


is_admin = st.session_state.admin

# ── Helpers ───────────────────────────────────────────────────────────────────

LIGHT_COLOURS = {"GREEN": "#00c853", "ORANGE": "#ff6d00", "RED": "#d50000"}
LIGHT_EMOJI = {"GREEN": "🟢", "ORANGE": "🟠", "RED": "🔴"}

# Plain-language one-liners so a visitor knows what each strategy actually does.
STRATEGY_DESC = {
    "markov_regime": "RSI signals, filtered by a bull/bear/sideways regime model",
    "rsi_meanrev": "Buys oversold dips, sells the bounce (mean reversion)",
    "ema_crossover": "Trend-following: fast EMA crosses slow, with a trend filter",
    "mtf_confluence": "Enters only when trend + MACD + RSI + VWAP all agree",
    "breakout": "Buys N-day highs, exits on lows (momentum breakout)",
    "daily_swing": "Daily swing trades from trend EMA + MACD + RSI (long & short)",
    "mtf_ls": "Multi-timeframe long/short via trend, MACD, RSI & VWAP bands",
    "bollinger": "Bollinger-band mean reversion with a trend-slope filter",
    "mtf_bb_vol": "Bollinger bands gated by a relative-volume spike",
    "regime_bb": "Bollinger bands gated by ADX trend strength + volume",
    "ensemble": "Votes across all the other strategies; trades on consensus",
    "bb_rsi_dip": "Buys dips below the lower Bollinger band when RSI is oversold; exits at a fixed % target",
    "xsec_momentum": "Market-neutral: ranks the whole crypto universe, longs the strongest / shorts the weakest (risk-parity, vol-targeted)",
}
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
def load_paper_accounts() -> dict:
    """The LIVE paper-trade ledger written by paper_trader.py (the real board)."""
    p = STATE_DIR / "paper_accounts.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


@st.cache_data(ttl=30)
def load_community() -> dict:
    """Attribution for community-suggested strategies: {strategy_name: {handle,
    idea, added}}. Written by Darren when he adds a weekly pick to the race."""
    p = STATE_DIR / "community_strategies.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


@st.cache_data(ttl=30)
def load_equity_history(max_points: int = 49) -> dict:
    """Recent per-strategy standings (return %) for the race replay, from the tail
    of state/equity_history.jsonl. Returns {name: [ret%, ...]} + '__btc__'. Empty
    if not enough history yet (the component then eases start->now instead)."""
    p = STATE_DIR / "equity_history.jsonl"
    if not p.exists():
        return {}
    rows = []
    for line in p.read_text().splitlines()[-max_points:]:
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if len(rows) < 6:
        return {}
    series: dict[str, list] = {}
    for r in rows:
        for name, eq in (r.get("eq") or {}).items():
            series.setdefault(name, []).append(round((eq / 1000.0 - 1.0) * 100, 3))
        if r.get("btc") is not None:
            series.setdefault("__btc__", []).append(round((r["btc"] / 1000.0 - 1.0) * 100, 3))
    return series


@st.cache_data(ttl=30)
def load_progress() -> dict:
    p = ROOT / "docs" / "PAPER" / "progress.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_submission(handle: str, idea: str) -> tuple[bool, str]:
    """Append a free-text strategy suggestion to state/submissions.jsonl. Text only,
    by design — no code is ever accepted or run. Light validation; Darren's weekly
    review is the real filter."""
    idea = (idea or "").strip()
    handle = (handle or "").strip() or "anonymous"
    if len(idea) < 12:
        return False, "Tell us a little more — what should it watch, and when should it buy or sell?"
    if len(idea) > 2000:
        return False, "That's a whole novel — trim it to the core idea: the data and the trigger."
    try:
        STATE_DIR.mkdir(exist_ok=True)
        with open(STATE_DIR / "submissions.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "handle": handle[:40], "idea": idea,
            }) + "\n")
        return True, f"🐢 Entry received, {handle}! Darren reviews the grid every week — watch this space."
    except Exception:
        return False, "Couldn't save that just now — give it another go in a moment."


_RACE_TEMPLATE = r"""
<!doctype html><html lang="en"><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');
:root{--ink:#0A0D18;--line:#28304C;--text:#EAEDF7;--muted:#8A93AD;--violet:#8B6CFF;--cyan:#2DD4DA;
--gold:#F5C451;--silver:#C9D2E3;--bronze:#D08A52;--red:#FB6F92;--steel:#7C89A8}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;color:var(--text);background:transparent;line-height:1.5}
.eyebrow{font-size:11px;letter-spacing:2.2px;text-transform:uppercase;color:var(--violet);font-weight:600}
.since{font-size:10.5px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);margin-top:3px;font-variant-numeric:tabular-nums}
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap;padding:20px 24px;
 border:1px solid var(--line);border-radius:16px;background:linear-gradient(135deg,rgba(139,108,255,.15),rgba(20,26,44,.5) 55%);margin-bottom:16px}
.hero h1{font-family:'Saira Condensed';font-weight:700;font-size:clamp(34px,6vw,56px);line-height:.95;margin:5px 0 4px}
.hero .sub{color:var(--muted);font-size:14px;max-width:50ch}.hero .sub b{color:var(--text);font-weight:600}
.leadstat{text-align:right;min-width:130px}
.leadstat .big{font-family:'Saira Condensed';font-weight:700;font-size:46px;line-height:1}
.leadstat .cap{font-size:10.5px;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted);margin-top:4px}
.bar{display:flex;align-items:center;gap:14px;margin:0 2px 10px}
.replay{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--violet);color:var(--text);background:rgba(139,108,255,.14);
 border-radius:10px;padding:7px 13px;font-weight:600;font-size:12.5px;cursor:pointer;font-family:inherit}
.replay:hover{background:rgba(139,108,255,.24)}
.clock{font-family:'IBM Plex Mono';font-size:12px;color:var(--cyan)}
.scrub{flex:1;height:4px;border-radius:3px;background:var(--line);position:relative;overflow:hidden}
.scrub i{position:absolute;left:0;top:0;bottom:0;width:0;background:linear-gradient(90deg,var(--violet),var(--cyan))}
.comm{display:flex;align-items:center;gap:10px;border:1px solid var(--line);border-left:3px solid var(--cyan);border-radius:10px;
 padding:9px 14px;margin-bottom:14px;background:rgba(20,26,44,.55);font-size:13px;min-height:40px}
.arena{border:1px solid var(--line);border-radius:16px;padding:6px 0;background:rgba(13,17,30,.55);overflow:hidden}
.lane{display:grid;grid-template-columns:38px 170px 1fr;align-items:center;gap:12px;padding:8px 16px;position:relative}
.lane+.lane{border-top:1px solid rgba(40,48,76,.5)}
.rk{font-family:'Saira Condensed';font-weight:700;font-size:20px;text-align:center;color:var(--muted)}
.who{min-width:0}
.nm{font-family:'Saira Condensed';font-weight:600;font-size:17px;letter-spacing:.3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.by{font-size:9.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.pickchip{color:var(--gold);font-weight:600;letter-spacing:.3px}
.track{position:relative;height:32px;border-radius:9px;border:1px solid rgba(40,48,76,.6);
 background:repeating-linear-gradient(90deg,rgba(255,255,255,.022) 0 2px,transparent 2px 46px)}
.startline{position:absolute;top:-4px;bottom:-4px;width:2px;background:rgba(234,237,247,.4)}
.btcline{position:absolute;top:-6px;bottom:-6px;width:2px;background:var(--cyan);box-shadow:0 0 8px rgba(45,212,218,.8)}
.btctag{position:absolute;top:-19px;font-size:9px;letter-spacing:.4px;color:var(--cyan);transform:translateX(-50%)}
.startag{position:absolute;top:-19px;font-size:9px;letter-spacing:.4px;color:rgba(234,237,247,.5);transform:translateX(-50%)}
.trail{position:absolute;top:50%;transform:translateY(-50%);height:9px;border-radius:6px;opacity:.5}
.runner{position:absolute;top:50%;transform:translate(-50%,-50%);height:24px;display:flex;align-items:center;gap:6px;
 padding:0 8px 0 5px;border-radius:13px;font-family:'IBM Plex Mono';font-weight:600;font-size:11.5px;white-space:nowrap;box-shadow:0 2px 9px rgba(0,0,0,.4)}
.runner .badge{width:15px;height:15px;border-radius:50%;display:grid;place-items:center;font-size:9px;font-weight:700;color:#0A0D18}
.foot{margin-top:16px;color:var(--muted);font-size:12px;display:flex;gap:20px;flex-wrap:wrap}.foot b{color:var(--text)}
@media (prefers-reduced-motion:reduce){.runner{transition:none}}
</style></head><body>
<div class="hero"><div>
  <div class="eyebrow">Leader on the board</div>
  <div class="since" id="since"></div>
  <h1 id="leadName">—</h1>
  <div class="sub">A live, public race — every strategy trades <b>$1,000</b> forward, fees in. Beat the field, and beat just <b>holding BTC</b>. No real money.</div>
</div><div class="leadstat"><div class="big" id="leadRet">—</div><div class="cap" id="leadCap"></div></div></div>
<div class="bar"><button class="replay" id="replayBtn">&#9654; Replay the race</button>
 <div class="clock" id="clock"></div><div class="scrub"><i id="scrubFill"></i></div></div>
<div class="comm"><span>&#127908;</span><span id="commLine"></span></div>
<div class="arena" id="arena"></div>
<div class="foot">
 <span><b>Position</b> = live P&amp;L. <b>Gold/silver/bronze</b> = top 3, <b style="color:#FB6F92">red</b> = backmarker.</span>
 <span><b style="color:#2DD4DA">Cyan line</b> = buy-and-hold BTC, the bar to beat.</span>
</div>
<script>
const DATA = __DATA__;
const med={1:'var(--gold)',2:'var(--silver)',3:'var(--bronze)'};
function color(r){ if(med[r.rank]) return getC(med[r.rank]);
  if(r.status==='RED' || (r.last && r.ret<0)) return getC('var(--red)'); return getC('var(--steel)'); }
function getC(v){const m={'var(--gold)':'#F5C451','var(--silver)':'#C9D2E3','var(--bronze)':'#D08A52','var(--red)':'#FB6F92','var(--steel)':'#7C89A8'};return m[v]||v;}
function hexA(h,a){const n=parseInt(h.slice(1),16);return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;}
const R=DATA.runners; const N=R.length; R.forEach((r,i)=>r.rank=i+1); if(N) R[N-1].last=true;
const allret=R.map(r=>r.ret).concat([DATA.btc]);
const lo=Math.min(...allret)-0.6, hi=Math.max(...allret)+0.6, span=(hi-lo)||1;
const X=v=>(v-lo)/span*100; const startX=X(0), btcX0=X(DATA.btc);
function easePath(end){const p=[];for(let k=0;k<=40;k++){const t=k/40;p.push(end*(1-Math.pow(1-t,2)));}return p;}
const H=DATA.history||{}; const hasH = H && Object.keys(H).length>2;
R.forEach(r=>{r.col=color(r); r.path=(hasH&&H[r.nm]&&H[r.nm].length>=6)?H[r.nm]:easePath(r.ret);});
const btcPath=(hasH&&H['__btc__']&&H['__btc__'].length>=6)?H['__btc__']:easePath(DATA.btc);
const PL=Math.max(...R.map(r=>r.path.length), btcPath.length);
const arena=document.getElementById('arena');
R.forEach((r,i)=>{
  const medal=r.rank<=3?['&#129351;','&#129352;','&#129353;'][r.rank-1]:r.rank;
  const badge=r.pos==='long'?'L':r.pos==='short'?'S':r.pos==='market-neutral'?'N':'·';
  const byHtml=r.by?`<div class="by">by @${r.by}${r.pick?' · <span class="pickchip">★ pick</span>':''}</div>`:(r.pick?'<div class="by"><span class="pickchip">★ pick</span></div>':'');
  const lane=document.createElement('div');lane.className='lane';
  lane.innerHTML=`<div class="rk">${medal}</div><div class="who"><div class="nm" title="${r.desc||''}">${r.nm}</div>${byHtml}</div>
   <div class="track">${i===0?`<div class="startag" style="left:${startX}%">$1,000</div><div class="btctag" data-bt style="left:${btcX0}%">BTC</div>`:''}
   <div class="startline" style="left:${startX}%"></div><div class="btcline" data-bl style="left:${btcX0}%"></div>
   <div class="trail" data-tr></div><div class="runner" data-rn><span class="badge">${badge}</span><span data-lb>0.0%</span></div></div>`;
  arena.appendChild(lane);
  r._rn=lane.querySelector('[data-rn]');r._lb=lane.querySelector('[data-lb]');r._tr=lane.querySelector('[data-tr]');
  r._rn.style.background=hexA(r.col,.16);r._rn.style.color=r.col;r._rn.style.border=`1px solid ${hexA(r.col,.55)}`;
  r._rn.querySelector('.badge').style.background=r.col;
  r._tr.style.background=`linear-gradient(90deg,transparent,${hexA(r.col,.6)})`;
  if(r.rank===1) r._rn.style.boxShadow=`0 0 16px ${hexA(r.col,.7)},0 2px 9px rgba(0,0,0,.5)`;
});
const blines=document.querySelectorAll('[data-bl]'), btag=document.querySelectorAll('[data-bt]');
const META=DATA.meta||{}; if(META.started) document.getElementById('since').textContent='Trading live since '+META.started+' · Day '+META.day;
document.getElementById('leadName').textContent = N?R[0].nm:'—';
document.getElementById('leadRet').textContent = N?((R[0].ret>=0?'+':'')+R[0].ret.toFixed(1)+'%'):'—';
document.getElementById('leadRet').style.color = N?R[0].col:'var(--text)';
document.getElementById('leadCap').textContent = N?('leader · '+((R[0].ret-DATA.btc>=0?'+':'')+(R[0].ret-DATA.btc).toFixed(1))+'% vs BTC'):'';
const lead=N?R[0].nm:'—', back=N?R[N-1].nm:'—';
const COMM=['&#127937; '+lead+' leads the field','&#128034; tight race — most still hugging the $1,000 line',
  '&#129460; '+back+' drifting to the back, near the cut','&#128184; only the front runners are clear of the BTC pace car'];
let t=0,playing=true,ci=0,lastC=-1;
const clock=document.getElementById('clock'),scrub=document.getElementById('scrubFill'),commLine=document.getElementById('commLine');
const TOTMIN=Math.min(240,(PL-1)*5);
function at(path,idx){const j=Math.min(path.length-1,Math.max(0,idx));return path[j];}
function frame(){
  if(playing){t+=0.006;if(t>=1){t=0;ci=0;lastC=-1;}}
  const idx=Math.floor(t*(PL-1));
  R.forEach(r=>{const v=at(r.path,idx),x=X(v);r._rn.style.left=x+'%';
    r._tr.style.left=startX+'%';r._tr.style.width=Math.max(0,x-startX)+'%';
    r._lb.textContent=(v>=0?'+':'')+v.toFixed(1)+'%';});
  const bx=X(at(btcPath,idx));blines.forEach(b=>b.style.left=bx+'%');btag.forEach(b=>b.style.left=bx+'%');
  const mins=Math.round((1-t)*TOTMIN);clock.textContent=t>0.97?'now':'−'+Math.floor(mins/60)+'h '+String(mins%60).padStart(2,'0')+'m';
  scrub.style.width=(t*100)+'%';
  const seg=Math.floor(t*COMM.length);if(seg!==lastC){commLine.innerHTML=COMM[Math.min(seg,COMM.length-1)];lastC=seg;}
  requestAnimationFrame(frame);
}
document.getElementById('replayBtn').addEventListener('click',()=>{t=0;ci=0;lastC=-1;playing=true;});
requestAnimationFrame(frame);
</script></body></html>
"""


def render_race_board(accounts: dict, meta: dict, bench: dict, history: dict,
                      community: dict | None = None) -> None:
    """Render the gamified live race board (custom HTML component) from the ledger."""
    community = community or {}
    # "This week's pick" = the most recently added community entry, within 7 days.
    recent_pick, pick_when = None, None
    for nm, c in community.items():
        try:
            d = datetime.fromisoformat(c.get("added", ""))
            d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if pick_when is None or d > pick_when:
            pick_when, recent_pick = d, nm
    if pick_when and (datetime.now(timezone.utc) - pick_when).days > 7:
        recent_pick = None

    runners = []
    for name, info in accounts.items():
        eq = info.get("equity", info.get("balance"))
        if eq is None:
            continue
        runners.append({
            "nm": name,
            "ret": round(info.get("return_pct", 0.0) or 0.0, 2),
            "status": info.get("light", "ORANGE"),
            "pos": info.get("side", "flat"),
            "desc": STRATEGY_DESC.get(name, "") or (community.get(name, {}).get("idea", "")[:80]),
            "by": community.get(name, {}).get("handle"),
            "pick": name == recent_pick,
        })
    runners.sort(key=lambda r: r["ret"], reverse=True)

    # Anchored race start = earliest account inception (persisted, stable).
    _MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    starts = []
    for info in accounts.values():
        s = info.get("start_ts")
        if s:
            try:
                d = datetime.fromisoformat(s)
                starts.append(d if d.tzinfo else d.replace(tzinfo=timezone.utc))
            except ValueError:
                pass
    started_label, day_n = "", 0
    if starts:
        bs = min(starts)
        day_n = (datetime.now(timezone.utc) - bs).days + 1
        started_label = f"{bs.day} {_MON[bs.month]} {bs.year}"

    data = {
        "runners": runners,
        "btc": round(bench.get("return_pct", 0.0) or 0.0, 2),
        "history": history or {},
        "meta": {"started": started_label, "day": day_n},
    }
    height = 330 + len(runners) * 50 + 70
    html = _RACE_TEMPLATE.replace("__DATA__", json.dumps(data))
    components.html(html, height=height, scrolling=False)
    return started_label, day_n


@st.cache_data(ttl=60)
def load_signals_report() -> tuple[str, str]:
    """The signal digest the VPS monitor writes. Returns (markdown, last-modified)."""
    p = STATE_DIR / "signals" / "report.md"
    if not p.exists():
        return "", ""
    from datetime import datetime, timezone

    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return p.read_text(encoding="utf-8"), mtime


@st.cache_data(ttl=60)
def load_recent_events(n: int = 40) -> pd.DataFrame:
    """Most recent items from the appended, deduped news/Trump event log."""
    p = STATE_DIR / "signals" / "news.jsonl"
    if not p.exists():
        return pd.DataFrame()
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append({
            "ts": d.get("ts") or d.get("captured_at") or "",
            "source": d.get("source", "?"),
            "title": (d.get("title") or d.get("summary") or "")[:140],
            "tags": ", ".join(d.get("tags", []) or []),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("ts", ascending=False).head(n)
    return df


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

st.sidebar.title("🚦 stratbot")

# Public sees only the live tournament. The hidden admin login unlocks the
# research timeline and the lake-backed strategy lab (kept, just gated).
PUBLIC_TABS = ["Traffic Light"]
LAKE_TABS = ["Equity Curves", "Walk-forward Folds", "Trade Log"]
ADMIN_TABS = ["Market Signals", "Research Progress"] + (LAKE_TABS if LAKE_AVAILABLE else [])
tab_options = PUBLIC_TABS + (ADMIN_TABS if is_admin else [])

# A single-option menu is pointless — only show the picker once the admin login
# has unlocked extra views; otherwise the page is just the live tournament.
if len(tab_options) > 1:
    tab_choice = st.sidebar.radio("View", tab_options, index=0)
else:
    tab_choice = tab_options[0]

# Strategy-lab controls only matter for admins viewing the lake-backed tabs.
if is_admin and LAKE_AVAILABLE:
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

render_admin_gate()

# ── Tab: Traffic Light ────────────────────────────────────────────────────────

if tab_choice == "Research Progress":
    st.title("Research Progress — Undergrad → Master's → PhD")
    st.markdown(
        "A build-in-public record of an ongoing research programme: **do a head of "
        "state's social-media posts move cryptocurrency markets**, and can AI be used "
        "as a genuine research collaborator along the way? Progress is tracked across "
        "three rigour tiers and updated as each piece of work lands and is committed."
    )
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

elif tab_choice == "Market Signals":
    st.title("Market Signals")
    report, mtime = load_signals_report()
    if not report:
        st.info(
            "No signal digest yet. The VPS monitor (`signals-monitor.timer`) writes "
            "`state/signals/report.md` every few hours — futures positioning, macro/"
            "cross-asset correlations, crypto news, and Trump Truth-Social posts."
        )
    else:
        st.caption(f"Digest generated {mtime} · futures · macro · news · Trump (Truth Social)")
        st.markdown(report)
        st.markdown("---")
        st.subheader("Latest events")
        ev = load_recent_events(60)
        if ev.empty:
            st.caption("No events captured yet.")
        else:
            is_trump = ev["source"].str.startswith("trump")
            tr, nw = ev[is_trump], ev[~is_trump]
            if not tr.empty:
                st.markdown("**🇺🇸 Trump · Truth Social** (latest)")
                st.dataframe(tr[["ts", "title"]].head(15), use_container_width=True, hide_index=True)
            if not nw.empty:
                st.markdown("**📰 Crypto / financial news** (latest)")
                st.dataframe(nw[["ts", "source", "title"]].head(30), use_container_width=True, hide_index=True)

elif tab_choice == "Traffic Light":
    with st.expander("How this race works"):
        st.markdown(
            "- **The grid:** every strategy starts at **$1,000** and trades the live feed "
            "forward. Its place on the track is its real balance — no made-up score.\n"
            "- **The podium:** 🥇🥈🥉 mark the top three; the **backmarker** turns red once "
            "it has a real track record (**14 days live or 20 trades**) and is then at risk "
            "of being cut.\n"
            "- **The pace car:** the cyan line is **buy-and-hold BTC** — the bar every "
            "strategy is really trying to beat.\n"
            "- **Genuinely out-of-sample:** strategies race forward in real time, on data "
            "that didn't exist when they were written — nothing curve-fit.\n"
            "- **Costs are real:** 0.1% taker fee + ~2bp slippage on every entry and exit.\n"
            "- **No auto-trading:** the live field is only ever changed by a human.\n"
            "- Updates every few minutes against a self-hosted price lake. "
            "*(Paper trading — no real money.)*"
        )

    ledger = load_paper_accounts()
    accounts = ledger.get("accounts", {})
    meta = ledger.get("meta", {})
    bench = ledger.get("benchmark", {})

    if not accounts:
        st.warning(
            "The live board is starting up — `paper_trader` hasn't written its first "
            "tick yet. Accounts begin at $1,000 and accumulate from here."
        )
    else:
        _updated = meta.get("last_tick_ts", "—")
        # ── the gamified live race board (custom HTML component) ────────────────
        _started, _day = render_race_board(accounts, meta, bench, load_equity_history(), load_community())
        _since = f"trading live since {_started} · day {_day} · " if _started else ""
        st.caption(
            f"Live · {_since}{len(accounts)} strategies trading $1,000 forward · "
            f"updated {_updated} · BTC regime: {meta.get('regime', '—')}"
        )

        def _money(x, signed=False):
            if x is None:
                return "—"
            sign = "+" if (signed and x >= 0) else ("-" if (signed and x < 0) else "")
            return f"{sign}${abs(x):,.0f}"

        with st.expander("Full standings & numbers"):
            rows = []
            for name, info in accounts.items():
                eq = info.get("equity", info.get("balance"))
                rows.append({
                    "name": name, "light": info.get("light", "ORANGE"), "equity": eq,
                    "pnl": info.get("pnl"), "ret": info.get("return_pct"),
                    "trades": info.get("trade_count", 0) or 0,
                    "win": info.get("win_rate", 0.0) or 0.0, "pos": info.get("side", "flat"),
                })
            rows.sort(key=lambda r: (r["equity"] is not None, r["equity"] if r["equity"] is not None else -1e9), reverse=True)
            table = [{
                "#": i + 1,
                "Strategy": r["name"],
                "What it does": STRATEGY_DESC.get(r["name"], "—"),
                "Balance": _money(r["equity"]),
                "P&L": _money(r["pnl"], signed=True),
                "Return": f"{r['ret']:+.1f}%" if r["ret"] is not None else "—",
                "Trades": r["trades"],
                "Win %": f"{r['win'] * 100:.0f}%" if r["trades"] else "—",
                "Now": r["pos"],
            } for i, r in enumerate(rows)]
            if bench.get("balance") is not None:
                table.append({
                    "#": "—", "Strategy": "Buy & Hold BTC", "What it does": "benchmark — just hold BTC",
                    "Balance": _money(bench.get("balance")),
                    "P&L": _money((bench.get("balance") or 0) - 1000.0, signed=True),
                    "Return": f"{bench.get('return_pct', 0):+.1f}%",
                    "Trades": "—", "Win %": "—", "Now": "hold",
                })
            st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    # ── Enter your own strategy (free-text, no code by design) ──────────────────
    st.markdown("---")
    st.subheader("🏁 Enter your own strategy")
    st.markdown(
        "Think you can beat the market? **Bring it down and we'll see if you're right** — "
        "no \"3000% bot\" claims here, just an honest, fees-included race.\n\n"
        "**No code, no jargon.** Every trading bot needs only two things: **data** (something it "
        "can watch) and a **trigger** (when to buy or sell). Tell us those — however weird and "
        "wonderful — and Darren will try to codify it.\n\n"
        "*For instance:* \"My tortoise Terry predicts BTC volume — when he sits top-right of his "
        "tank, volume rises the next day.\" Brilliant. Step one: insure Terry. Step two: if that's "
        "really the signal, the **data** is a camera on the tank and the **trigger** is *Terry "
        "top-right → expect higher volume* — wire that up and Terry races the field. Daft on "
        "purpose, but that's genuinely all a bot is."
    )
    with st.form("suggest_strategy", clear_on_submit=True):
        _handle = st.text_input("Your name or handle", max_chars=40, placeholder="e.g. terrys_human")
        _idea = st.text_area(
            "Your strategy idea", max_chars=2000,
            placeholder="What should it watch, and when should it buy or sell?",
        )
        _sent = st.form_submit_button("Enter the race →")
    if _sent:
        _ok, _msg = save_submission(_handle, _idea)
        (st.success if _ok else st.warning)(_msg)
    st.caption(
        "Darren reviews entries weekly, codifies the best idea he can, and adds it to the "
        "board — credited to you. Paper trading only, no real money."
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
