import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime
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
    .stApp { background-color: #090c10; color: #c9d1d9; font-family: 'Inter', -apple-system, sans-serif; }
    .main-title { font-size: 2.4rem; font-weight: 800; color: #ffffff; letter-spacing: -1px; margin-bottom: 0px; background: -webkit-linear-gradient(#fff, #8b949e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .sub-title { font-size: 0.95rem; color: #8b949e; margin-bottom: 20px; border-bottom: 1px solid #21262d; padding-bottom: 15px; }
    .trade-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 22px; margin-bottom: 18px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5); transition: all 0.2s ease-in-out; }
    .trade-card:hover { transform: translateY(-3px); box-shadow: 0 6px 16px rgba(0,0,0,0.6); }
    .trade-card-long { border-top: 4px solid #2ea043; }
    .trade-card-short { border-top: 4px solid #f85149; }
    .card-header { font-size: 1.3rem; font-weight: 700; color: #f0f6fc; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;}
    .card-metric { display: flex; justify-content: space-between; margin: 8px 0; font-size: 0.92rem; color: #c9d1d9; }
    .metric-label { color: #8b949e; font-weight: 500; }
    .num { font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }
    .badge { background:#21262d; padding:4px 10px; border-radius:12px; font-size:0.75rem; color:#c9d1d9; white-space:nowrap; display:inline-block; margin-bottom: 5px; font-weight: 500;}
    .badge-good { background: rgba(46,160,67,0.15); color:#3fb950; border:1px solid rgba(46,160,67,0.4); }
    .badge-warn { background: rgba(248,81,73,0.15); color:#ff7b72; border:1px solid rgba(248,81,73,0.4); }
    .score-track { background:#21262d; border-radius:8px; height:8px; width:100%; overflow:hidden; margin-top:6px; margin-bottom: 12px; border: 1px solid #30363d;}
    .score-fill-long { background: linear-gradient(90deg, #238636, #2ea043); height:100%; }
    .score-fill-short { background: linear-gradient(90deg, #da3633, #f85149); height:100%; }
    .disclaimer { font-size:0.75rem; color:#8b949e; margin-top:40px; padding-top:15px; border-top:1px solid #21262d; line-height:1.6; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⚡ Nexus Quant Scalper</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Algorithmic Multi-Timeframe Matrix • Powered by Hyperliquid & CoinDCX Perpetual Data</div>', unsafe_allow_html=True)

# ============================================================================
# CONSTANTS & CACHING
# ============================================================================
HISTORY_BARS = 200
CACHE_TTL_SECONDS = 5
MAX_WORKERS = 20

ALL_DCX_COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "NEAR", "LINK", "PEPE", "WIF", "SUI", "APT", "INJ", "ARB", "OP"]

# ============================================================================
# GLOBAL FUTURES MARKET LAYER (Hyperliquid DEX - Geo-Immune)
# ============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_global_futures_market():
    """Fetches full perpetuals context (Funding, OI, Volume) via Hyperliquid DEX."""
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "metaAndAssetCtxs"}
    try:
        res = requests.post(url, json=payload, timeout=5.0)
        if res.status_code == 200:
            data = res.json()
            universe, ctxs = data[0]["universe"], data[1]
            market_dict = {}
            for i, asset in enumerate(universe):
                coin = asset["name"]
                ctx = ctxs[i]
                mark_px = float(ctx.get("markPx", 0))
                prev_px = float(ctx.get("prevDayPx", 1))
                market_dict[coin] = {
                    "turnover": float(ctx.get("dayNtlVlm", 0)),
                    "chg_pct": ((mark_px - prev_px) / prev_px * 100) if prev_px > 0 else 0,
                    "funding_rate": float(ctx.get("funding", 0)),
                    "oi_usd": float(ctx.get("openInterest", 0)) * mark_px
                }
            return market_dict
    except:
        pass
    return {}

GLOBAL_MARKET = fetch_global_futures_market()
if GLOBAL_MARKET:
    ALL_COINS_DYNAMIC = sorted(list(set([c for c, d in GLOBAL_MARKET.items() if d.get("turnover", 0) > 2000000] + ALL_DCX_COINS)))
else:
    ALL_COINS_DYNAMIC = sorted(ALL_DCX_COINS)

# ============================================================================
# SESSION STATE & SIDEBAR
# ============================================================================
if "active_watchlist" not in st.session_state:
    st.session_state.active_watchlist = ["BTC", "ETH", "SOL", "PEPE", "SUI", "WIF"]

def apply_preset(preset_type: str):
    df_mkt = pd.DataFrame.from_dict(GLOBAL_MARKET, orient='index') if GLOBAL_MARKET else pd.DataFrame()
    if preset_type == "Majors":
        st.session_state.active_watchlist = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX"]
    elif preset_type == "Volume" and not df_mkt.empty and 'turnover' in df_mkt.columns:
        st.session_state.active_watchlist = df_mkt.sort_values(by="turnover", ascending=False).head(20).index.tolist()
    elif preset_type == "Momentum" and not df_mkt.empty and 'chg_pct' in df_mkt.columns:
        df_mkt['abs_chg'] = df_mkt['chg_pct'].abs()
        st.session_state.active_watchlist = df_mkt.sort_values(by="abs_chg", ascending=False).head(20).index.tolist()
    elif preset_type == "Clear":
        st.session_state.active_watchlist = []

st.sidebar.markdown("### 🔍 Market Screener")
valid_defaults = [coin for coin in st.session_state.active_watchlist if coin in ALL_COINS_DYNAMIC]
selected_coins = st.sidebar.multiselect("Active Scanning Matrix (Top Priority):", options=ALL_COINS_DYNAMIC, default=valid_defaults, key="matrix_multiselect")
st.session_state.active_watchlist = selected_coins

st.sidebar.markdown("---")
st.sidebar.markdown("**Global Smart Presets:**")
col1, col2 = st.sidebar.columns(2)
col1.button("🔥 Top Volume", on_click=apply_preset, args=("Volume",), use_container_width=True)
col2.button("🚀 Top Momentum", on_click=apply_preset, args=("Momentum",), use_container_width=True)
col3, col4 = st.sidebar.columns(2)
col3.button("💎 Default Majors", on_click=apply_preset, args=("Majors",), use_container_width=True)
col4.button("🗑️ Clear Matrix", on_click=apply_preset, args=("Clear",), use_container_width=True)

st.sidebar.markdown("---")
timeframe = st.sidebar.selectbox("Signal Resolution", ["1m", "5m", "15m"], index=1)
enable_mtf = st.sidebar.checkbox("Require HTF (15m) Trend", value=True)
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
    df['EMA_9'], df['EMA_21'] = df['close'].ewm(span=9, adjust=False).mean(), df['close'].ewm(span=21, adjust=False).mean()
    df['MACD'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    delta = df['close'].diff()
    gain, loss = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(), -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    df.loc[(gain == 0) & (loss == 0), 'RSI'] = 50.0

    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
    df['ATR_Pct'] = (df['ATR'] / df['close']) * 100
    df['Vol_Ratio'] = df['volume'] / df['volume'].rolling(window=20).mean().replace(0, np.nan)
    return df

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_candles(coin_symbol: str, tf: str):
    """Fetches pure futures candlestick data."""
    # 1. Primary: CoinDCX (Binance Futures Liquidity)
    url_coindcx = f"https://public.coindcx.com/market_data/candles/?pair=B-{coin_symbol}_USDT&interval={tf}&limit={HISTORY_BARS}"
    try:
        res = requests.get(url_coindcx, timeout=4.0)
        if res.status_code == 200 and isinstance(res.json(), list) and len(res.json()) > 30:
            df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
            return calculate_indicators(df), "CoinDCX"
    except: pass

    # 2. Secondary: Hyperliquid (DEX)
    hl_interval = {"1m": "1m", "5m": "5m", "15m": "15m"}.get(tf, "5m")
    hl_ms = {"1m": 60000, "5m": 300000, "15m": 900000}.get(tf, 300000)
    end_time = int(time.time() * 1000)
    
    url_hl = "https://api.hyperliquid.xyz/info"
    payload = {"type": "candleSnapshot", "req": {"coin": coin_symbol, "interval": hl_interval, "startTime": end_time - (HISTORY_BARS * hl_ms), "endTime": end_time}}
    try:
        res = requests.post(url_hl, json=payload, timeout=4.0)
        if res.status_code == 200 and isinstance(res.json(), list) and len(res.json()) > 30:
            df = pd.DataFrame(res.json()).rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
            for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
            return calculate_indicators(df), "Hyperliquid"
    except: pass

    return None, None

# ============================================================================
# EVALUATION & FORMATTING
# ============================================================================
def format_price(p):
    if p is None or pd.isna(p): return "-"
    return f"{p:,.2f}" if p >= 1000 else f"{p:.4f}" if p >= 1 else f"{p:.5f}" if p >= 0.01 else f"{p:.7f}"

def format_compact(n):
    if not n or pd.isna(n): return "N/A"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= div: return f"{n/div:.2f}{unit}"
    return f"{n:.2f}"

def evaluate_signal(coin_name: str):
    df, source = fetch_candles(coin_name, timeframe)
    if df is None or df.empty: return {"Coin": coin_name, "Error": True}

    last = df.iloc[-1]
    price, atr, rsi = last['close'], last['ATR'], last['RSI']
    bull_ema, bear_ema = last['EMA_9'] > last['EMA_21'], last['EMA_9'] < last['EMA_21']
    bull_macd, bear_macd = last['MACD_Hist'] > 0, last['MACD_Hist'] < 0

    mtf_aligned, htf_status = True, "N/A"
    if enable_mtf and timeframe != "15m":
        df_htf, _ = fetch_candles(coin_name, "15m")
        if df_htf is not None and not df_htf.empty:
            htf_bullish = df_htf.iloc[-1]['EMA_9'] > df_htf.iloc[-1]['EMA_21']
            htf_status = "BULL" if htf_bullish else "BEAR"
            if (bull_ema and not htf_bullish) or (bear_ema and htf_bullish): mtf_aligned = False

    direction = "LONG" if bull_ema and bull_macd and mtf_aligned else "SHORT" if bear_ema and bear_macd and mtf_aligned else "NONE"
    
    mkt = GLOBAL_MARKET.get(coin_name, {})
    funding, oi = mkt.get("funding_rate"), mkt.get("oi_usd")

    entry, sl, tp, lev, risk_pct = price, 0, 0, 1, 0.0
    if direction == "LONG": sl, tp = price - (sl_atr_mult * atr), price + (tp_atr_mult * atr)
    elif direction == "SHORT": sl, tp = price + (sl_atr_mult * atr), price - (tp_atr_mult * atr)

    if direction != "NONE":
        risk_pct = abs(entry - sl) / entry
        lev = int(min(max(1.0 / (liq_buffer_mult * risk_pct + 0.005), 2), 50))
    
    liq_price = (entry * (1 - 1.0/lev + 0.005)) if direction == "LONG" else (entry * (1 + 1.0/lev - 0.005)) if direction == "SHORT" else None
    pos_usd = (account_balance * (risk_per_trade_pct/100)) / risk_pct if risk_pct > 0 else 0
    
    score = 0.0
    if direction != "NONE":
        score += min(abs(last['MACD_Hist']) / (atr * 0.15 + 1e-12), 1.0) * 35
        score += min(max((last['Vol_Ratio'] - 1.0) / 1.5, 0.0), 1.0) * 25
        score += 20 if (direction == "LONG" and 40<rsi<70) or (direction == "SHORT" and 30<rsi<60) else 5
        score += 20 if (direction == htf_status) else 0

    return {
        "Coin": coin_name, "Signal": f"{direction} {'🟢' if direction=='LONG' else '🔴' if direction=='SHORT' else '⚪'}",
        "Direction": direction, "Price": format_price(price), "Entry": format_price(entry), "SL": format_price(sl), "TP": format_price(tp),
        "Lev": f"{lev}x", "LiqPrice": format_price(liq_price) if liq_price else "-", "PosUSD": pos_usd, "Score": round(min(score, 100.0), 1),
        "HTF": htf_status, "MACD": "🟢 Bull" if bull_macd else "🔴 Bear", "RSI": round(rsi, 1), "ATR": f"{last['ATR_Pct']:.2f}%", 
        "Funding": funding, "OI": oi, "Source": source, "Error": False
    }

# ============================================================================
# EXECUTION & RENDERING
# ============================================================================
if refresh_clicked:
    fetch_candles.clear()
    fetch_global_futures_market.clear()

results, failed = [], []
if st.session_state.active_watchlist:
    with st.spinner(f"Scanning via Perpetual Futures Matrix..."):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            raw_results = list(executor.map(evaluate_signal, st.session_state.active_watchlist))
        results = [r for r in raw_results if not r.get("Error")]

if results:
    df = pd.DataFrame(results)
    active_setups = df[df['Direction'] != "NONE"].sort_values("Score", ascending=False)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔍 Matrix Size", f"{len(results)} Coins")
    col2.metric("🟢 Active Longs", len(active_setups[active_setups['Direction'] == 'LONG']))
    col3.metric("🔴 Active Shorts", len(active_setups[active_setups['Direction'] == 'SHORT']))
    col4.metric("⏱️ Last Scan", datetime.now().strftime("%H:%M:%S"))

    st.markdown("---")
    st.markdown("### ⚡ Validated Prime Setups")

    if not active_setups.empty:
        cols = st.columns(3)
        for i, (_, row) in enumerate(active_setups.iterrows()):
            fund_color = "badge badge-warn" if row['Funding'] and ((row['Funding'] if row['Direction'] == "LONG" else -row['Funding']) > 0.0004) else "badge badge-good" if row['Funding'] and ((row['Funding'] if row['Direction'] == "LONG" else -row['Funding']) < 0) else "badge"
            card_html = f"""
            <div class="trade-card {'trade-card-long' if row['Direction']=='LONG' else 'trade-card-short'}">
                <div class="card-header"><span>{row['Coin']}-PERP</span><span class="{'metric-value-long' if row['Direction']=='LONG' else 'metric-value-short'}" style="font-size:0.85rem; border:1px solid currentColor; padding:3px 10px; border-radius:12px;">{row['Direction']}</span></div>
                <div class="card-metric"><span class="metric-label">Entry Price</span><span class="num" style="color:#f0f6fc;">${row['Entry']}</span></div>
                <div class="card-metric"><span class="metric-label">Stop-Loss</span><span class="num" style="color:#8b949e;">${row['SL']}</span></div>
                <div class="card-metric"><span class="metric-label">Take-Profit</span><span class="num" style="color:#f0f6fc;">${row['TP']}</span></div>
                <div class="card-metric"><span class="metric-label">Est. Liq ({row['Lev']})</span><span class="num" style="color:#d29922;">${row['LiqPrice']}</span></div>
                <hr style="border:0; height:1px; background:#30363d; margin:14px 0;">
                <div class="card-metric"><span class="metric-label">Algorithmic Confluence</span><span class="num">{row['Score']:.0f}/100</span></div>
                <div class="score-track"><div class="{'score-fill-long' if row['Direction']=='LONG' else 'score-fill-short'}" style="width:{row['Score']}%;"></div></div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:12px;">
                    <span class="badge">HTF {row['HTF']}</span><span class="{fund_color}">Fund {f"{row['Funding']*100:+.4f}%" if row['Funding'] else "N/A"}</span>
                    <span class="badge">OI ${format_compact(row['OI'])}</span><span class="badge" style="color:#8b949e;">{row['Source']}</span>
                </div>
                <div class="card-metric" style="margin-top:14px;"><span class="metric-label">Suggested Sizing</span><span class="num" style="color:#f0f6fc;">${row['PosUSD']:,.0f}</span></div>
            </div>"""
            cols[i % 3].markdown(card_html, unsafe_allow_html=True)
    else: st.info("Market is currently chopping or resolving. No high-conviction momentum setups passed the strict risk criteria.")

    st.markdown("---")
    st.markdown("### 📊 Live Matrix Data")
    view_df = df[['Coin', 'Signal', 'Price', 'HTF', 'MACD', 'RSI', 'ATR', 'Score']].sort_values(by=['Score', 'Coin'], ascending=[False, True])
    st.dataframe(view_df.style.map(lambda x: 'color: #3fb950; font-weight: bold;' if 'LONG' in str(x) or 'Bull' in str(x) else ('color: #f85149; font-weight: bold;' if 'SHORT' in str(x) or 'Bear' in str(x) else ''), subset=['Signal', 'MACD', 'HTF']), column_config={"Score": st.column_config.ProgressColumn("Setup Score", min_value=0, max_value=100, format="%.0f")}, use_container_width=True, hide_index=True)

st.markdown('<div class="disclaimer">Educational quantitative tool. Cryptocurrency futures carry a high degree of risk.</div>', unsafe_allow_html=True)
if auto_refresh: time.sleep(15); st.rerun()
