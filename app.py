import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import re
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Pro Quant Terminal",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INSTITUTIONAL UI / CSS
# ============================================================================
st.markdown("""
<style>
    .stApp {
        background-color: #090c10;
        color: #c9d1d9;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -1px;
        margin-bottom: 0px;
        background: -webkit-linear-gradient(#fff, #8b949e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #8b949e;
        margin-bottom: 20px;
        border-bottom: 1px solid #21262d;
        padding-bottom: 15px;
    }
    
    /* Trade Card Styling */
    .trade-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 22px;
        margin-bottom: 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        transition: all 0.2s ease-in-out;
    }
    .trade-card:hover { transform: translateY(-3px); box-shadow: 0 6px 16px rgba(0,0,0,0.6); }
    .trade-card-long { border-top: 4px solid #2ea043; }
    .trade-card-long:hover { border-color: #2ea043; box-shadow: 0 0 15px rgba(46, 160, 67, 0.15); }
    .trade-card-short { border-top: 4px solid #f85149; }
    .trade-card-short:hover { border-color: #f85149; box-shadow: 0 0 15px rgba(248, 81, 73, 0.15); }

    /* Typography inside cards */
    .card-header { font-size: 1.3rem; font-weight: 700; color: #f0f6fc; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;}
    .card-metric { display: flex; justify-content: space-between; margin: 8px 0; font-size: 0.92rem; color: #c9d1d9; }
    .metric-label { color: #8b949e; font-weight: 500; }
    .metric-value-long { color: #3fb950; font-weight: 600; }
    .metric-value-short { color: #ff7b72; font-weight: 600; }
    .num { font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }

    /* Badges */
    .badge { background:#21262d; padding:4px 10px; border-radius:12px; font-size:0.75rem; color:#c9d1d9; white-space:nowrap; display:inline-block; margin-bottom: 5px; font-weight: 500;}
    .badge-good { background: rgba(46,160,67,0.15); color:#3fb950; border:1px solid rgba(46,160,67,0.4); }
    .badge-warn { background: rgba(248,81,73,0.15); color:#ff7b72; border:1px solid rgba(248,81,73,0.4); }

    /* Setup strength bar */
    .score-track { background:#21262d; border-radius:8px; height:8px; width:100%; overflow:hidden; margin-top:6px; margin-bottom: 12px; border: 1px solid #30363d;}
    .score-fill-long { background: linear-gradient(90deg, #238636, #2ea043); height:100%; }
    .score-fill-short { background: linear-gradient(90deg, #da3633, #f85149); height:100%; }

    /* Footer disclaimer */
    .disclaimer { font-size:0.75rem; color:#8b949e; margin-top:40px; padding-top:15px; border-top:1px solid #21262d; line-height:1.6; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⚡ Nexus Quant Scalper</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Algorithmic Multi-Timeframe Matrix • Global Orderbook & Liquidation Analysis</div>', unsafe_allow_html=True)

# ============================================================================
# CONSTANTS & CACHING
# ============================================================================
HISTORY_BARS = 200
CACHE_TTL_SECONDS = 5
MAX_WORKERS = 20

def normalize_ticker(raw_input: str) -> str:
    return raw_input.strip().upper().replace("USDT", "").replace("B-", "")

# ============================================================================
# NETWORK & GLOBAL MARKET LAYER (Optimized)
# ============================================================================
def _safe_get_json(url: str, timeout: float = 4.0, retries: int = 1):
    headers = {"User-Agent": "Mozilla/5.0 (NexusQuant/3.0)"}
    for attempt in range(retries + 1):
        try:
            res = requests.get(url, headers=headers, timeout=timeout)
            if res.status_code == 200:
                return res.json()
        except requests.exceptions.RequestException:
            pass
        if attempt < retries:
            time.sleep(0.3)
    return None

@st.cache_data(ttl=30, show_spinner=False)
def fetch_global_market():
    """Fetches ALL perpetual futures data in ONE call to build dynamic presets and save API limits."""
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    data = _safe_get_json(url)
    market_dict = {}
    if data and data.get("result", {}).get("list"):
        for t in data["result"]["list"]:
            symbol = t.get("symbol", "")
            if symbol.endswith("USDT"):
                coin = symbol.replace("USDT", "")
                try:
                    market_dict[coin] = {
                        "turnover": float(t.get("turnover24h", 0)),
                        "chg_pct": float(t.get("price24hPcnt", 0)) * 100,
                        "funding_rate": float(t.get("fundingRate") or 0),
                        "next_funding_ms": int(t.get("nextFundingTime") or 0),
                        "oi_usd": float(t.get("openInterestValue") or 0),
                        "last_price": float(t.get("lastPrice") or 0),
                        "bid": float(t.get("bid1Price") or 0),
                        "ask": float(t.get("ask1Price") or 0)
                    }
                except (TypeError, ValueError):
                    continue
    return market_dict

GLOBAL_MARKET = fetch_global_market()
ALL_COINS_DYNAMIC = sorted(list(GLOBAL_MARKET.keys())) if GLOBAL_MARKET else ["BTC", "ETH", "SOL", "XRP"]

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if "active_watchlist" not in st.session_state:
    st.session_state.active_watchlist = ["BTC", "ETH", "SOL", "PEPE", "SUI", "WIF"]

# Preset Callbacks
def apply_preset(preset_type: str):
    if not GLOBAL_MARKET:
        return
    df_mkt = pd.DataFrame.from_dict(GLOBAL_MARKET, orient='index')
    
    if preset_type == "Majors":
        st.session_state.active_watchlist = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX"]
    elif preset_type == "Volume":
        top_vol = df_mkt.sort_values(by="turnover", ascending=False).head(20).index.tolist()
        st.session_state.active_watchlist = top_vol
    elif preset_type == "Momentum":
        # Top absolute movers (highest gainers + biggest losers)
        df_mkt['abs_chg'] = df_mkt['chg_pct'].abs()
        top_mom = df_mkt.sort_values(by="abs_chg", ascending=False).head(20).index.tolist()
        st.session_state.active_watchlist = top_mom
    elif preset_type == "Clear":
        st.session_state.active_watchlist = []

def add_from_dropdown_callback():
    val = st.session_state.get("coin_dropdown_selection")
    if val and val not in st.session_state.active_watchlist:
        st.session_state.active_watchlist.append(val)

# ============================================================================
# SIDEBAR — SCREENER
# ============================================================================
st.sidebar.markdown("### 🔍 Market Screener")
st.sidebar.selectbox("Select Asset:", options=ALL_COINS_DYNAMIC, key="coin_dropdown_selection")
st.sidebar.button("➕ Add to Matrix", on_click=add_from_dropdown_callback, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Global Smart Presets:**")
col1, col2 = st.sidebar.columns(2)
col1.button("🔥 Top Volume", on_click=apply_preset, args=("Volume",), use_container_width=True)
col2.button("🚀 Top Momentum", on_click=apply_preset, args=("Momentum",), use_container_width=True)
col3, col4 = st.sidebar.columns(2)
col3.button("💎 Default Majors", on_click=apply_preset, args=("Majors",), use_container_width=True)
col4.button("🗑️ Clear Matrix", on_click=apply_preset, args=("Clear",), use_container_width=True)

st.sidebar.markdown("---")
# Filter the watchlist to only include coins that actually exist in the fetched options
valid_defaults = [coin for coin in st.session_state.active_watchlist if coin in ALL_COINS_DYNAMIC]

selected_coins = st.sidebar.multiselect(
    "Active Scanning Matrix (Top Priority):",
    options=ALL_COINS_DYNAMIC,
    default=valid_defaults,
    key="matrix_multiselect"
)
st.session_state.active_watchlist = selected_coins

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Quant Parameters")
timeframe = st.sidebar.selectbox("Signal Resolution", ["1m", "5m", "15m"], index=1)
enable_mtf = st.sidebar.checkbox("Require HTF (15m) Trend Alignment", value=True)
auto_refresh = st.sidebar.checkbox("Live Auto-Refresh (15s)", value=False)
refresh_clicked = st.sidebar.button("🔄 Force Scan Now", type="primary", use_container_width=True)

with st.sidebar.expander("🧮 Risk & Sizing Engine"):
    account_balance = st.number_input("Account Balance (USD)", value=1000.0, step=100.0)
    risk_per_trade_pct = st.slider("Risk per Trade (%)", 0.1, 5.0, 1.0, 0.1)
    sl_atr_mult = st.slider("Stop-Loss (ATR mult)", 0.5, 4.0, 1.5, 0.1)
    tp_atr_mult = st.slider("Take-Profit (ATR mult)", 1.0, 8.0, 3.0, 0.1)
    liq_buffer_mult = st.slider("Liquidation Buffer", 1.0, 4.0, 2.0, 0.1)

# ============================================================================
# INDICATOR ENGINE
# ============================================================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()

    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    delta = df['close'].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df.loc[(gain == 0) & (loss == 0), 'RSI'] = 50.0

    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
    df['ATR_Pct'] = (df['ATR'] / df['close']) * 100

    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['volume'] / df['Vol_SMA'].replace(0, np.nan)
    
    tp = (df['high'] + df['low'] + df['close']) / 3
    df['VWAP'] = (tp * df['volume']).cumsum() / df['volume'].cumsum().replace(0, np.nan)
    
    return df

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_candles(coin_symbol: str, tf: str):
    interval = {"1m": "1", "5m": "5", "15m": "15"}.get(tf, "5")
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={coin_symbol}USDT&interval={interval}&limit={HISTORY_BARS}"
    data = _safe_get_json(url)
    if data and len(data.get("result", {}).get("list", [])) > 30:
        rows = data["result"]["list"]
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover']).iloc[::-1].reset_index(drop=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return calculate_indicators(df)
    return None

# ============================================================================
# EVALUATION & FORMATTING
# ============================================================================
def format_price(p):
    if p is None or pd.isna(p): return "-"
    if p >= 1000: return f"{p:,.2f}"
    if p >= 1: return f"{p:.4f}"
    if p >= 0.01: return f"{p:.5f}"
    return f"{p:.7f}"

def format_compact(n):
    if not n or pd.isna(n): return "N/A"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= div: return f"{n/div:.2f}{unit}"
    return f"{n:.2f}"

def evaluate_signal(coin_name: str):
    df = fetch_candles(coin_name, timeframe)
    if df is None or df.empty: return {"Coin": coin_name, "Error": True}

    last = df.iloc[-1]
    price = last['close']
    atr, rsi = last['ATR'], last['RSI']
    
    bull_ema = last['EMA_9'] > last['EMA_21']
    bull_macd = last['MACD_Hist'] > 0
    bear_ema = last['EMA_9'] < last['EMA_21']
    bear_macd = last['MACD_Hist'] < 0

    mtf_aligned = True
    htf_status = "N/A"
    if enable_mtf and timeframe != "15m":
        df_htf = fetch_candles(coin_name, "15m")
        if df_htf is not None and not df_htf.empty:
            htf_last = df_htf.iloc[-1]
            htf_bullish = htf_last['EMA_9'] > htf_last['EMA_21']
            htf_status = "BULL" if htf_bullish else "BEAR"
            if (bull_ema and not htf_bullish) or (bear_ema and htf_bullish):
                mtf_aligned = False

    direction = "NONE"
    if bull_ema and bull_macd and mtf_aligned: direction = "LONG"
    elif bear_ema and bear_macd and mtf_aligned: direction = "SHORT"

    # Grab pre-fetched global market data instead of API calls
    mkt = GLOBAL_MARKET.get(coin_name, {})
    funding = mkt.get("funding_rate")
    oi = mkt.get("oi_usd")
    spread_pct = ((mkt.get("ask", 0) - mkt.get("bid", 0)) / price * 100) if mkt.get("ask") else 0

    entry, sl, tp, lev, risk_pct = price, 0, 0, 1, 0.0
    if direction == "LONG":
        sl, tp = price - (sl_atr_mult * atr), price + (tp_atr_mult * atr)
    elif direction == "SHORT":
        sl, tp = price + (sl_atr_mult * atr), price - (tp_atr_mult * atr)

    if direction != "NONE":
        risk_pct = abs(entry - sl) / entry
        raw_lev = 1.0 / (liq_buffer_mult * risk_pct + 0.005) # 0.5% MMR assumption
        lev = int(min(max(raw_lev, 2), 50))
    
    liq_price = None
    if direction == "LONG": liq_price = entry * (1 - 1.0/lev + 0.005)
    elif direction == "SHORT": liq_price = entry * (1 + 1.0/lev - 0.005)

    pos_usd = (account_balance * (risk_per_trade_pct/100)) / risk_pct if risk_pct > 0 else 0
    
    # Heuristic scoring
    score = 0.0
    if direction != "NONE":
        score += min(abs(last['MACD_Hist']) / (atr * 0.15 + 1e-12), 1.0) * 35
        score += min(max((last['Vol_Ratio'] - 1.0) / 1.5, 0.0), 1.0) * 25
        score += 20 if (direction == "LONG" and 40<rsi<70) or (direction == "SHORT" and 30<rsi<60) else 5
        score += 20 if (direction == htf_status) else 0

    return {
        "Coin": coin_name, "Signal": f"{direction} {'🟢' if direction=='LONG' else '🔴' if direction=='SHORT' else '⚪'}",
        "Direction": direction, "Price": format_price(price), "Entry": format_price(entry),
        "SL": format_price(sl), "TP": format_price(tp), "Lev": f"{lev}x",
        "LiqPrice": format_price(liq_price) if liq_price else "-",
        "PosUSD": pos_usd, "Score": round(min(score, 100.0), 1),
        "HTF": htf_status, "MACD": "🟢 Bull" if bull_macd else "🔴 Bear",
        "RSI": round(rsi, 1), "ATR": f"{last['ATR_Pct']:.2f}%", 
        "Vol": f"{last['Vol_Ratio']:.1f}x", "Funding": funding, "OI": oi, "Spread": spread_pct,
        "Link": f"https://www.bybit.com/trade/usdt/{coin_name}USDT", "Error": False
    }

# ============================================================================
# EXECUTION
# ============================================================================
if refresh_clicked:
    fetch_candles.clear()
    fetch_global_market.clear()

results, failed = [], []
if st.session_state.active_watchlist:
    with st.spinner(f"Scanning {len(st.session_state.active_watchlist)} assets via algorithmic matrix..."):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            raw_results = list(executor.map(evaluate_signal, st.session_state.active_watchlist))
        results = [r for r in raw_results if not r.get("Error")]
        failed = [r["Coin"] for r in raw_results if r.get("Error")]

if failed:
    st.toast(f"⚠️ Failed to fetch {len(failed)} assets. They may be delisted or untradable.")

# ============================================================================
# RENDERING DASHBOARD
# ============================================================================
if results:
    df = pd.DataFrame(results)
    
    # Dash Metrics
    col1, col2, col3, col4 = st.columns(4)
    active_setups = df[df['Direction'] != "NONE"].sort_values("Score", ascending=False)
    
    col1.metric("🔍 Matrix Size", f"{len(results)} Coins")
    col2.metric("🟢 Active Longs", len(active_setups[active_setups['Direction'] == 'LONG']))
    col3.metric("🔴 Active Shorts", len(active_setups[active_setups['Direction'] == 'SHORT']))
    col4.metric("⏱️ Last Scan", datetime.now().strftime("%H:%M:%S"))

    st.markdown("---")
    st.markdown("### ⚡ Validated Prime Setups")

    if not active_setups.empty:
        cols = st.columns(3)
        for i, (_, row) in enumerate(active_setups.iterrows()):
            fund_color = "badge"
            if row['Funding'] is not None:
                crowd = row['Funding'] if row['Direction'] == "LONG" else -row['Funding']
                if crowd > 0.0004: fund_color = "badge badge-warn"
                elif crowd < 0: fund_color = "badge badge-good"
            
            fund_txt = f"{row['Funding']*100:+.4f}%" if row['Funding'] is not None else "N/A"
            oi_txt = format_compact(row['OI'])

            card_html = f"""
            <div class="trade-card {'trade-card-long' if row['Direction']=='LONG' else 'trade-card-short'}">
                <div class="card-header">
                    <span>{row['Coin']}-PERP</span>
                    <span class="{'metric-value-long' if row['Direction']=='LONG' else 'metric-value-short'}" style="font-size:0.85rem; border:1px solid currentColor; padding:3px 10px; border-radius:12px;">{row['Direction']}</span>
                </div>
                <div class="card-metric"><span class="metric-label">Entry Price</span><span class="num" style="color:#f0f6fc;">${row['Entry']}</span></div>
                <div class="card-metric"><span class="metric-label">Stop-Loss</span><span class="num" style="color:#8b949e;">${row['SL']}</span></div>
                <div class="card-metric"><span class="metric-label">Take-Profit</span><span class="num" style="color:#f0f6fc;">${row['TP']}</span></div>
                <div class="card-metric"><span class="metric-label">Est. Liq ({row['Lev']})</span><span class="num" style="color:#d29922;">${row['LiqPrice']}</span></div>
                
                <hr style="border:0; height:1px; background:#30363d; margin:14px 0;">
                
                <div class="card-metric"><span class="metric-label">Algorithmic Confluence</span><span class="num">{row['Score']:.0f}/100</span></div>
                <div class="score-track"><div class="{'score-fill-long' if row['Direction']=='LONG' else 'score-fill-short'}" style="width:{row['Score']}%;"></div></div>
                
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:12px;">
                    <span class="badge">HTF {row['HTF']}</span>
                    <span class="badge">MACD {row['MACD']}</span>
                    <span class="{fund_color}">Fund {fund_txt}</span>
                    <span class="badge">OI ${oi_txt}</span>
                </div>
                
                <div class="card-metric" style="margin-top:14px;"><span class="metric-label">Suggested Sizing</span><span class="num" style="color:#f0f6fc;">${row['PosUSD']:,.0f}</span></div>
                
                <div style="margin-top:16px;">
                    <a href="{row['Link']}" target="_blank" style="color:#58a6ff; text-decoration:none; font-size:0.85rem; font-weight:600;">↗ Execute Trade on Bybit</a>
                </div>
            </div>
            """
            cols[i % 3].markdown(card_html, unsafe_allow_html=True)
    else:
        st.info("Market is currently chopping or resolving. No high-conviction momentum setups passed the strict risk criteria.")

    st.markdown("---")
    st.markdown("### 📊 Live Matrix Data")
    
    view_df = df[['Coin', 'Signal', 'Price', 'HTF', 'MACD', 'RSI', 'ATR', 'Vol', 'Score', 'Link']].copy()
    view_df = view_df.sort_values(by=['Score', 'Coin'], ascending=[False, True])
    
    st.dataframe(
        view_df.style.map(lambda x: 'color: #3fb950; font-weight: bold;' if 'LONG' in str(x) or 'Bull' in str(x) else ('color: #f85149; font-weight: bold;' if 'SHORT' in str(x) or 'Bear' in str(x) else ''), subset=['Signal', 'MACD', 'HTF']),
        column_config={
            "Link": st.column_config.LinkColumn("Action", display_text="Trade ↗"),
            "Score": st.column_config.ProgressColumn("Setup Score", min_value=0, max_value=100, format="%.0f"),
        },
        use_container_width=True,
        hide_index=True
    )

st.markdown('<div class="disclaimer">Educational quantitative tool. Cryptocurrency futures carry a high degree of risk. Estimated liquidation assumes 0.5% MMR on isolated margin.</div>', unsafe_allow_html=True)

if auto_refresh:
    time.sleep(15)
    st.rerun()
