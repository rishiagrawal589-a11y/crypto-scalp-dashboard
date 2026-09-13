import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Nexus Quant Terminal | Scalp Pro",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INSTITUTIONAL UI STYLING (CSS)
# ============================================================================
st.markdown("""
<style>
    .stApp {
        background-color: #090c10;
        color: #c9d1d9;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -1px;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 0.92rem;
        color: #8b949e;
        margin-bottom: 20px;
        border-bottom: 1px solid #21262d;
        padding-bottom: 12px;
    }
    
    /* Institutional Trade Cards */
    .trade-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        transition: transform 0.15s ease;
        position: relative;
    }
    .trade-card:hover { transform: translateY(-2px); }
    .trade-card-long { border-top: 4px solid #2ea043; }
    .trade-card-short { border-top: 4px solid #f85149; }
    
    /* #1 Best Setup Highlighting */
    .trade-card-top {
        border: 1px solid #d29922 !important;
        border-top: 5px solid #e3b341 !important;
        box-shadow: 0 0 20px rgba(227, 179, 65, 0.18) !important;
    }
    .top-badge {
        background: linear-gradient(90deg, #d29922, #f59e0b);
        color: #000;
        font-size: 0.72rem;
        font-weight: 800;
        padding: 3px 8px;
        border-radius: 6px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 10px;
        display: inline-block;
    }

    .card-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f0f6fc;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .card-metric {
        display: flex;
        justify-content: space-between;
        margin: 6px 0;
        font-size: 0.88rem;
        color: #c9d1d9;
    }
    .metric-label { color: #8b949e; font-weight: 500; }
    .num { font-variant-numeric: tabular-nums; font-family: 'JetBrains Mono', monospace; }
    
    /* Dynamic Entry Banners */
    .entry-banner-in {
        background: rgba(46,160,67,0.15);
        border: 1px solid rgba(46,160,67,0.4);
        color: #3fb950;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        text-align: center;
        margin: 8px 0;
    }
    .entry-banner-chase {
        background: rgba(248,81,73,0.12);
        border: 1px solid rgba(248,81,73,0.35);
        color: #ff7b72;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        text-align: center;
        margin: 8px 0;
    }
    .entry-banner-wait {
        background: rgba(210,153,34,0.15);
        border: 1px solid rgba(210,153,34,0.35);
        color: #e3b341;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        text-align: center;
        margin: 8px 0;
    }
    .adverse-warning {
        background: rgba(248,81,73,0.1);
        border-left: 3px solid #f85149;
        color: #ff7b72;
        padding: 6px 10px;
        font-size: 0.75rem;
        border-radius: 0 6px 6px 0;
        margin-top: 8px;
        line-height: 1.4;
    }
    
    .badge {
        background:#21262d;
        padding:3px 8px;
        border-radius:8px;
        font-size:0.72rem;
        color:#c9d1d9;
        white-space:nowrap;
        display:inline-block;
        font-weight: 500;
    }
    .score-track {
        background:#21262d;
        border-radius:6px;
        height:6px;
        width:100%;
        overflow:hidden;
        margin-top:4px;
        margin-bottom: 10px;
    }
    .score-fill { height:100%; }
    .disclaimer {
        font-size:0.75rem;
        color:#8b949e;
        margin-top:40px;
        padding-top:15px;
        border-top:1px solid #21262d;
        line-height:1.6;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⚡ Nexus Quant Scalper</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Perpetual Futures Confluence Scanner • Real-Time Entry Zone & Duration Engine</div>', unsafe_allow_html=True)

# ============================================================================
# CONSTANTS & CACHING
# ============================================================================
HISTORY_BARS = 200
CACHE_TTL = 5
MAX_WORKERS = 20

BASE_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "NEAR", "LINK", 
    "PEPE", "WIF", "SUI", "APT", "INJ", "ARB", "OP", "TIA", "SEI", "FET"
]

def normalize_ticker(raw_input: str) -> str:
    cleaned = raw_input.strip().upper().replace("USDT", "").replace("B-", "")
    return re.sub(r'[^A-Z0-9]', '', cleaned)

# ============================================================================
# GLOBAL FUTURES MARKET LAYER (Hyperliquid DEX - Zero Geo-Blocking)
# ============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_global_futures_market():
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "metaAndAssetCtxs"}
    try:
        res = requests.post(url, json=payload, timeout=4.5)
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
    except Exception:
        pass
    return {}

GLOBAL_MARKET = fetch_global_futures_market()
DYNAMIC_COINS = sorted(list(set(
    [c for c, d in GLOBAL_MARKET.items() if d.get("turnover", 0) > 1500000] + BASE_COINS
)))

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if "custom_coins_added" not in st.session_state:
    st.session_state.custom_coins_added = []

# Merge standard options with user-added custom tokens
ALL_AVAILABLE_OPTIONS = sorted(list(set(DYNAMIC_COINS + st.session_state.custom_coins_added)))

if "matrix_multiselect" not in st.session_state:
    default_init = ["BTC", "ETH", "SOL", "PEPE", "SUI", "WIF"]
    st.session_state.matrix_multiselect = [c for c in default_init if c in ALL_AVAILABLE_OPTIONS]

# Preset Callbacks
def apply_preset(preset_type: str):
    df_mkt = pd.DataFrame.from_dict(GLOBAL_MARKET, orient='index') if GLOBAL_MARKET else pd.DataFrame()
    if preset_type == "Majors":
        target = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX"]
    elif preset_type == "Volume" and not df_mkt.empty and 'turnover' in df_mkt.columns:
        target = df_mkt.sort_values(by="turnover", ascending=False).head(20).index.tolist()
    elif preset_type == "Momentum" and not df_mkt.empty and 'chg_pct' in df_mkt.columns:
        df_mkt['abs_chg'] = df_mkt['chg_pct'].abs()
        target = df_mkt.sort_values(by="abs_chg", ascending=False).head(20).index.tolist()
    elif preset_type == "Clear":
        target = []
    else:
        target = ["BTC", "ETH", "SOL"]
    
    st.session_state.matrix_multiselect = [c for c in target if c in ALL_AVAILABLE_OPTIONS]

def add_custom_ticker():
    raw = st.session_state.custom_ticker_input
    normalized = normalize_ticker(raw)
    if normalized and len(normalized) >= 2:
        if normalized not in st.session_state.custom_coins_added:
            st.session_state.custom_coins_added.append(normalized)
        if normalized not in st.session_state.matrix_multiselect:
            st.session_state.matrix_multiselect.insert(0, normalized)
    st.session_state.custom_ticker_input = ""

# ============================================================================
# SIDEBAR
# ============================================================================
st.sidebar.markdown("### 🔍 Market Screener")

st.sidebar.text_input("➕ Add Custom Coin (e.g. KAS, APT):", key="custom_ticker_input", on_change=add_custom_ticker)

st.sidebar.markdown("**Global Smart Presets:**")
col1, col2 = st.sidebar.columns(2)
col1.button("🔥 Top Volume", on_click=apply_preset, args=("Volume",), use_container_width=True)
col2.button("🚀 Top Momentum", on_click=apply_preset, args=("Momentum",), use_container_width=True)
col3, col4 = st.sidebar.columns(2)
col3.button("💎 Default Majors", on_click=apply_preset, args=("Majors",), use_container_width=True)
col4.button("🗑️ Clear Matrix", on_click=apply_preset, args=("Clear",), use_container_width=True)

# Synchronize options to prevent StreamlitDefaultNotInOptionsError
CURRENT_OPTIONS = sorted(list(set(DYNAMIC_COINS + st.session_state.custom_coins_added)))
st.session_state.matrix_multiselect = [c for c in st.session_state.matrix_multiselect if c in CURRENT_OPTIONS]

selected_coins = st.sidebar.multiselect(
    "Active Scanning Matrix:",
    options=CURRENT_OPTIONS,
    key="matrix_multiselect"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Quant Parameters")
timeframe = st.sidebar.selectbox("Signal Resolution (TF)", ["1m", "5m", "15m"], index=1)
enable_mtf = st.sidebar.checkbox("Require 15m HTF Alignment", value=True)
auto_refresh = st.sidebar.checkbox("Live Auto-Refresh (15s)", value=False)
refresh_clicked = st.sidebar.button("🔄 Force Scan Now", type="primary", use_container_width=True)

with st.sidebar.expander("🧮 Risk & Precision Execution"):
    account_balance = st.number_input("Account Balance ($)", value=1000.0, step=100.0)
    risk_per_trade_pct = st.slider("Risk Per Trade (%)", 0.1, 5.0, 1.0, 0.1)
    sl_atr_mult = st.slider("Stop-Loss (x ATR)", 0.5, 4.0, 1.5, 0.1)
    tp_atr_mult = st.slider("Take-Profit (x ATR)", 1.0, 8.0, 3.0, 0.1)
    liq_buffer_mult = st.slider("Liquidation Safety Buffer", 1.0, 4.0, 2.0, 0.1)

# ============================================================================
# INDICATORS & DATA PIPELINE
# ============================================================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['MACD'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    delta = df['close'].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    df.loc[(gain == 0) & (loss == 0), 'RSI'] = 50.0

    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
    df['ATR_Pct'] = (df['ATR'] / df['close']) * 100
    df['Vol_Ratio'] = df['volume'] / df['volume'].rolling(window=20).mean().replace(0, np.nan)
    
    tp = (df['high'] + df['low'] + df['close']) / 3
    df['VWAP'] = (tp * df['volume']).cumsum() / df['volume'].cumsum().replace(0, np.nan)
    return df

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_candles(coin_symbol: str, tf: str):
    # Tier 1: CoinDCX Futures (Routes Binance Perp Liquidity)
    url_coindcx = f"https://public.coindcx.com/market_data/candles/?pair=B-{coin_symbol}_USDT&interval={tf}&limit={HISTORY_BARS}"
    try:
        res = requests.get(url_coindcx, timeout=3.5)
        if res.status_code == 200 and isinstance(res.json(), list) and len(res.json()) > 30:
            df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return calculate_indicators(df), "CoinDCX"
    except Exception:
        pass

    # Tier 2: Hyperliquid DEX (Zero geo-restrictions)
    hl_interval = {"1m": "1m", "5m": "5m", "15m": "15m"}.get(tf, "5m")
    hl_ms = {"1m": 60000, "5m": 300000, "15m": 900000}.get(tf, 300000)
    end_time = int(time.time() * 1000)
    url_hl = "https://api.hyperliquid.xyz/info"
    payload = {
        "type": "candleSnapshot",
        "req": {"coin": coin_symbol, "interval": hl_interval, "startTime": end_time - (HISTORY_BARS * hl_ms), "endTime": end_time}
    }
    try:
        res = requests.post(url_hl, json=payload, timeout=3.5)
        if res.status_code == 200 and isinstance(res.json(), list) and len(res.json()) > 30:
            df = pd.DataFrame(res.json()).rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return calculate_indicators(df), "Hyperliquid"
    except Exception:
        pass

    return None, None

# ============================================================================
# EVALUATION & SIGNALS
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
    if df is None or df.empty:
        return {"Coin": coin_name, "Error": True}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    price, atr, rsi = last['close'], last['ATR'], last['RSI']
    
    bull_ema, bear_ema = last['EMA_9'] > last['EMA_21'], last['EMA_9'] < last['EMA_21']
    bull_macd, bear_macd = last['MACD_Hist'] > 0, last['MACD_Hist'] < 0

    mtf_aligned, htf_status = True, "N/A"
    if enable_mtf and timeframe != "15m":
        df_htf, _ = fetch_candles(coin_name, "15m")
        if df_htf is not None and not df_htf.empty:
            htf_bullish = df_htf.iloc[-1]['EMA_9'] > df_htf.iloc[-1]['EMA_21']
            htf_status = "BULL" if htf_bullish else "BEAR"
            if (bull_ema and not htf_bullish) or (bear_ema and htf_bullish):
                mtf_aligned = False

    direction = "LONG" if bull_ema and bull_macd and mtf_aligned else "SHORT" if bear_ema and bear_macd and mtf_aligned else "NONE"
    
    # Execution targets
    entry = price
    sl = price - (sl_atr_mult * atr) if direction == "LONG" else price + (sl_atr_mult * atr) if direction == "SHORT" else 0
    tp = price + (tp_atr_mult * atr) if direction == "LONG" else price - (tp_atr_mult * atr) if direction == "SHORT" else 0
    
    # Entry zone validation
    entry_status, entry_css = "NEUTRAL", "entry-banner-wait"
    entry_low, entry_high = 0, 0
    if direction == "LONG":
        entry_low = entry - (0.25 * atr)
        entry_high = entry + (0.15 * atr)
        if entry_low <= price <= entry_high:
            entry_status, entry_css = "🎯 IN PRIME ENTRY ZONE", "entry-banner-in"
        elif price > entry_high:
            entry_status, entry_css = "⚠️ OVEREXTENDED (Chasing Risk)", "entry-banner-chase"
        else:
            entry_status, entry_css = "⏳ WAIT FOR PULLBACK TO ZONE", "entry-banner-wait"
    elif direction == "SHORT":
        entry_low = entry - (0.15 * atr)
        entry_high = entry + (0.25 * atr)
        if entry_low <= price <= entry_high:
            entry_status, entry_css = "🎯 IN PRIME ENTRY ZONE", "entry-banner-in"
        elif price < entry_low:
            entry_status, entry_css = "⚠️ OVEREXTENDED (Chasing Risk)", "entry-banner-chase"
        else:
            entry_status, entry_css = "⏳ WAIT FOR PULLBACK TO ZONE", "entry-banner-wait"

    # Expected trade duration calculation
    tf_minutes = {"1m": 1, "5m": 5, "15m": 15}.get(timeframe, 5)
    tp_distance = abs(tp - price)
    expected_bars = max(1.0, tp_distance / (atr * 0.65 + 1e-9))
    est_minutes = int(expected_bars * tf_minutes)
    tp_duration_str = f"~{est_minutes}–{int(est_minutes * 1.5)} min" if direction != "NONE" else "N/A"

    # Adverse momentum warnings
    adverse_warning = None
    if direction == "LONG":
        if last['MACD_Hist'] < prev['MACD_Hist']:
            adverse_warning = "⚠️ Warning: MACD histogram momentum decelerating."
        elif price < last['EMA_9']:
            adverse_warning = "⚠️ Caution: Price losing 9 EMA dynamic support."
        elif price < last['VWAP']:
            adverse_warning = "⚠️ Caution: Price lost Session VWAP."
    elif direction == "SHORT":
        if last['MACD_Hist'] > prev['MACD_Hist']:
            adverse_warning = "⚠️ Warning: Bearish momentum slowing (MACD curling up)."
        elif price > last['EMA_9']:
            adverse_warning = "⚠️ Caution: Price piercing above 9 EMA resistance."
        elif price > last['VWAP']:
            adverse_warning = "⚠️ Caution: Price reclaimed Session VWAP."

    risk_pct = abs(entry - sl) / entry if direction != "NONE" and entry > 0 else 0.0
    lev = int(min(max(1.0 / (liq_buffer_mult * risk_pct + 0.005), 2), 50)) if direction != "NONE" else 1
    liq_price = (entry * (1 - 1.0/lev + 0.005)) if direction == "LONG" else (entry * (1 + 1.0/lev - 0.005)) if direction == "SHORT" else None
    pos_usd = (account_balance * (risk_per_trade_pct/100)) / risk_pct if risk_pct > 0 else 0

    score = 0.0
    if direction != "NONE":
        score += min(abs(last['MACD_Hist']) / (atr * 0.15 + 1e-12), 1.0) * 35
        score += min(max((last['Vol_Ratio'] - 1.0) / 1.5, 0.0), 1.0) * 25
        score += 20 if (direction == "LONG" and 45 < rsi < 70) or (direction == "SHORT" and 30 < rsi < 55) else 5
        score += 20 if (direction == htf_status) else 0

    mkt = GLOBAL_MARKET.get(coin_name, {})
    return {
        "Coin": coin_name, "Signal": direction, "Price": format_price(price),
        "RawPrice": price, "Entry": format_price(entry), "SL": format_price(sl), "TP": format_price(tp),
        "EntryZone": f"${format_price(entry_low)} - ${format_price(entry_high)}",
        "EntryStatus": entry_status, "EntryCSS": entry_css,
        "TPDuration": tp_duration_str, "AdverseWarning": adverse_warning,
        "Lev": f"{lev}x", "LiqPrice": format_price(liq_price) if liq_price else "-", "PosUSD": pos_usd,
        "Score": round(min(score, 100.0), 1), "HTF": htf_status, "MACD": "🟢 Bull" if bull_macd else "🔴 Bear",
        "RSI": round(rsi, 1), "ATR": f"{last['ATR_Pct']:.2f}%", "Vol": f"{last['Vol_Ratio']:.1f}x",
        "Funding": mkt.get("funding_rate"), "OI": mkt.get("oi_usd"), "Source": source, "Error": False
    }

# ============================================================================
# EXECUTION & SCANNER
# ============================================================================
if refresh_clicked:
    fetch_candles.clear()
    fetch_global_futures_market.clear()

results = []
if selected_coins:
    with st.spinner(f"Scanning {len(selected_coins)} assets via Confluence Engine..."):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            raw = list(executor.map(evaluate_signal, selected_coins))
        results = [r for r in raw if not r.get("Error")]

# ============================================================================
# RENDERING
# ============================================================================
if results:
    df = pd.DataFrame(results)
    active_setups = df[df['Signal'] != "NONE"].sort_values("Score", ascending=False).reset_index(drop=True)
    
    # Top Stats
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Assets Analyzed", f"{len(results)}")
    m2.metric("🟢 Active Longs", len(active_setups[active_setups['Signal'] == 'LONG']))
    m3.metric("🔴 Active Shorts", len(active_setups[active_setups['Signal'] == 'SHORT']))
    m4.metric("Last Refresh", datetime.now().strftime("%H:%M:%S"))

    st.markdown("---")
    st.markdown("### ⚡ Validated Scalp Trade Setups")

    if not active_setups.empty:
        cols = st.columns(3)
        for i, row in active_setups.iterrows():
            is_top = (i == 0)
            card_class = "trade-card-long" if row['Signal'] == "LONG" else "trade-card-short"
            if is_top: card_class += " trade-card-top"
            
            fill_color = "linear-gradient(90deg, #238636, #2ea043)" if row['Signal'] == "LONG" else "linear-gradient(90deg, #da3633, #f85149)"
            top_badge_html = '<div class="top-badge">⭐ #1 Top Confluence Setup</div>' if is_top else ''
            warning_html = f'<div class="adverse-warning">{row["AdverseWarning"]}</div>' if row['AdverseWarning'] else ''

            # Zero-indent string to prevent Streamlit Markdown from interpreting it as raw code
            card_html = (
                f'<div class="trade-card {card_class}">'
                f'{top_badge_html}'
                f'<div class="card-header">'
                f'<span>{row["Coin"]}-PERP</span>'
                f'<span style="font-size:0.85rem; border:1px solid currentColor; padding:3px 10px; border-radius:12px; font-weight:700; color:{"#3fb950" if row["Signal"]=="LONG" else "#ff7b72"};">'
                f'{row["Signal"]}</span>'
                f'</div>'
                f'<div class="{row["EntryCSS"]}">{row["EntryStatus"]}</div>'
                f'<div class="card-metric"><span class="metric-label">Ideal Entry Pocket</span><span class="num" style="color:#f0f6fc;">{row["EntryZone"]}</span></div>'
                f'<div class="card-metric"><span class="metric-label">Stop-Loss (SL)</span><span class="num" style="color:#8b949e;">${row["SL"]}</span></div>'
                f'<div class="card-metric"><span class="metric-label">Target (TP)</span><span class="num" style="color:#f0f6fc;">${row["TP"]}</span></div>'
                f'<div class="card-metric"><span class="metric-label">Est. Time to TP</span><span class="num" style="color:#38bdf8; font-weight:600;">{row["TPDuration"]}</span></div>'
                f'<div class="card-metric"><span class="metric-label">Est. Liq ({row["Lev"]})</span><span class="num" style="color:#e3b341;">${row["LiqPrice"]}</span></div>'
                f'{warning_html}'
                f'<hr style="border:0; height:1px; background:#30363d; margin:12px 0;">'
                f'<div class="card-metric"><span class="metric-label">Setup Strength</span><span class="num">{row["Score"]:.0f}/100</span></div>'
                f'<div class="score-track"><div class="score-fill" style="background:{fill_color}; width:{row["Score"]}%;"></div></div>'
                f'<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;">'
                f'<span class="badge">HTF {row["HTF"]}</span>'
                f'<span class="badge">RSI {row["RSI"]}</span>'
                f'<span class="badge">Vol {row["Vol"]}</span>'
                f'<span class="badge" style="color:#8b949e;">{row["Source"]}</span>'
                f'</div>'
                f'<div class="card-metric" style="margin-top:12px;"><span class="metric-label">Suggested Position</span><span class="num" style="color:#f0f6fc;">${row["PosUSD"]:,.0f}</span></div>'
                f'</div>'
            )
            
            try:
                cols[i % 3].html(card_html)
            except AttributeError:
                cols[i % 3].markdown(card_html, unsafe_allow_html=True)
    else:
        st.info("Market is currently consolidating. No high-conviction scalping confluence detected.")

    st.markdown("---")
    st.markdown("### 📊 Market Confluence Table")
    view_df = df[['Coin', 'Signal', 'Price', 'EntryZone', 'EntryStatus', 'TPDuration', 'HTF', 'Score']].sort_values(by=['Score', 'Coin'], ascending=[False, True])
    st.dataframe(
        view_df.style.map(lambda x: 'color: #3fb950; font-weight: bold;' if 'LONG' in str(x) else ('color: #f85149; font-weight: bold;' if 'SHORT' in str(x) else ''), subset=['Signal']),
        column_config={
            "Score": st.column_config.ProgressColumn("Setup Score", min_value=0, max_value=100, format="%.0f"),
            "EntryZone": "Optimal Pocket",
            "EntryStatus": "Execution Status",
            "TPDuration": "Est. Duration"
        },
        use_container_width=True,
        hide_index=True
    )

st.markdown('<div class="disclaimer">Algorithmic execution scanner. Perpetual futures trading involves market risk. Always confirm execution order on your primary exchange.</div>', unsafe_allow_html=True)

if auto_refresh:
    time.sleep(15)
    st.rerun()
