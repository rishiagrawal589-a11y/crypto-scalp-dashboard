import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Page Configuration
st.set_page_config(
    page_title="CoinDCX Quant Terminal",
    layout="wide",
    page_icon="💠",
    initial_sidebar_state="expanded"
)

# Professional Institutional UI / Dark Theme CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0b0e14;
        color: #d1d5db;
        font-family: 'Inter', sans-serif;
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #9ca3af;
        margin-bottom: 25px;
        border-bottom: 1px solid #1f2937;
        padding-bottom: 15px;
    }
    /* Trade Card Styling */
    .trade-card {
        background: linear-gradient(145deg, #111827 0%, #0d1117 100%);
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .trade-card-long { border-top: 4px solid #10b981; }
    .trade-card-short { border-top: 4px solid #ef4444; }
    
    .card-header { font-size: 1.2rem; font-weight: 700; color: #f3f4f6; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;}
    .card-metric { display: flex; justify-content: space-between; margin: 5px 0; font-size: 0.88rem; color: #d1d5db; }
    .metric-label { color: #9ca3af; font-weight: 500; }
    .metric-value-long { color: #10b981; font-weight: 600; }
    .metric-value-short { color: #ef4444; font-weight: 600; }
    
    .warning-box {
        background-color: #451a03;
        border: 1px solid #b45309;
        color: #fde68a;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 10px;
    }
    .status-badge {
        background: #1e293b;
        color: #38bdf8;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">💠 Algorithmic Momentum Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Real-Time Trade Tracking • Zero-Liquidation Safety Filter • Early Reversal Warnings</div>', unsafe_allow_html=True)

# Symbol Normalization Map
SYMBOL_MAP = {
    "ARBITRUM": "ARB", "SHIBA": "SHIB", "SHIBAINU": "SHIB", "DOGECOIN": "DOGE",
    "MATIC": "POL", "RIPPLE": "XRP", "SOLANA": "SOL", "CARDANO": "ADA",
    "AVALANCHE": "AVAX", "POLKADOT": "DOT"
}

# Master Ticker Database
ALL_DCX_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "NEAR", "LINK",
    "PEPE", "SHIB", "WIF", "BONK", "FLOKI", "SUI", "APT", "INJ", "FET", "RENDER",
    "ARB", "OP", "TIA", "SEI", "STX", "FIL", "LTC", "BCH", "POL", "GALA",
    "LDO", "RUNE", "ATOM", "ETC", "ICP", "DOT", "UNI", "AAVE", "SAND", "MANA", "KAS"
]

def normalize_ticker(raw_input):
    cleaned = raw_input.strip().upper().replace("USDT", "").replace("B-", "")
    return SYMBOL_MAP.get(cleaned, cleaned)

# Session State Initialization
if "active_watchlist" not in st.session_state:
    st.session_state.active_watchlist = ["BTC", "ETH", "SOL", "PEPE", "SUI", "ARB", "WIF", "INJ"]

# Callbacks
def add_from_dropdown_callback():
    normalized = normalize_ticker(st.session_state.coin_dropdown_selection)
    if normalized and normalized not in st.session_state.active_watchlist:
        st.session_state.active_watchlist.append(normalized)

def add_from_manual_callback():
    if st.session_state.manual_text_input:
        normalized = normalize_ticker(st.session_state.manual_text_input)
        if normalized not in ALL_DCX_COINS: ALL_DCX_COINS.insert(0, normalized)
        if normalized not in st.session_state.active_watchlist: st.session_state.active_watchlist.append(normalized)
        st.session_state.manual_text_input = ""

def add_preset_memes():
    for coin in ["PEPE", "DOGE", "SHIB", "WIF", "BONK"]:
        if coin not in st.session_state.active_watchlist: st.session_state.active_watchlist.append(coin)

def add_preset_l1s():
    for coin in ["SOL", "AVAX", "SUI", "APT", "NEAR", "SEI"]:
        if coin not in st.session_state.active_watchlist: st.session_state.active_watchlist.append(coin)

# Sidebar Controls
st.sidebar.markdown("### 🔄 Control Panel")

# 1. Dedicated Manual Refresh Button
if st.sidebar.button("⚡ Refresh Data Now", use_container_width=True, type="primary"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Add Asset to Watchlist")
st.sidebar.selectbox("Select Asset from Directory:", options=ALL_DCX_COINS, key="coin_dropdown_selection")
st.sidebar.button("➕ Add Selected Asset", on_click=add_from_dropdown_callback, use_container_width=True)

st.sidebar.text_input("Or Input Custom Ticker:", key="manual_text_input", on_change=add_from_manual_callback)
st.sidebar.button("➕ Add Manual Asset", on_click=add_from_manual_callback, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Sector Quick Presets:**")
col_p1, col_p2 = st.sidebar.columns(2)
col_p1.button("🔥 Memes", on_click=add_preset_memes, use_container_width=True)
col_p2.button("🚀 L1s/L2s", on_click=add_preset_l1s, use_container_width=True)

st.sidebar.markdown("---")
selected_coins = st.sidebar.multiselect(
    "Active Scanning Matrix:",
    options=list(dict.fromkeys(ALL_DCX_COINS + st.session_state.active_watchlist)),
    default=st.session_state.active_watchlist,
    key="active_watchlist"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Risk & Timing Controls")
timeframe = st.sidebar.selectbox("Signal Resolution (TF)", ["1m", "5m", "15m"], index=1)
enable_mtf = st.sidebar.checkbox("Require 15m HTF Alignment", value=True)
strict_vol = st.sidebar.checkbox("Require Volume Spike (Strict)", value=True)
auto_refresh = st.sidebar.checkbox("Live Auto-Refresh (10s)", value=False)

def calculate_indicators(df):
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    # MACD
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss.replace(0, 0.00001))
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['ATR'] = np.max(ranges, axis=1).rolling(14).mean()

    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    return df

def fetch_data(coin_symbol, tf):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://public.coindcx.com/market_data/candles/?pair=B-{coin_symbol}_USDT&interval={tf}&limit=60"
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200 and isinstance(res.json(), list) and len(res.json()) > 20:
            df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
            return calculate_indicators(df)
    except: pass
    
    try:
        bybit_interval = {"1m": "1", "5m": "5", "15m": "15"}.get(tf, "5")
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={coin_symbol}USDT&interval={bybit_interval}&limit=60"
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200 and len(res.json().get("result", {}).get("list", [])) > 20:
            df = pd.DataFrame(res.json()["result"]["list"], columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover']).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
            return calculate_indicators(df)
    except: pass
    return None

def format_price(price):
    if price >= 1000: return f"{price:.2f}"
    elif price >= 1: return f"{price:.4f}"
    elif price >= 0.01: return f"{price:.5f}"
    else: return f"{price:.7f}"

def evaluate_signal(coin_name):
    df = fetch_data(coin_name, timeframe)
    if df is None or df.empty:
        return {"Coin": coin_name, "Error": True}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    rsi = round(last['RSI'], 1) if not np.isnan(last['RSI']) else 50.0
    atr = last['ATR'] if not np.isnan(last['ATR']) else price * 0.01
    
    vol_spike = last['volume'] > (last['Vol_SMA'] * 1.3)
    
    bull_ema = last['EMA_9'] > last['EMA_21']
    bull_macd = last['MACD_Hist'] > 0
    bear_ema = last['EMA_9'] < last['EMA_21']
    bear_macd = last['MACD_Hist'] < 0

    mtf_aligned = True
    htf_status = "N/A"
    if enable_mtf and timeframe != "15m":
        df_htf = fetch_data(coin_name, "15m")
        if df_htf is not None and not df_htf.empty:
            htf_last = df_htf.iloc[-1]
            htf_bullish = htf_last['EMA_9'] > htf_last['EMA_21']
            htf_status = "BULL" if htf_bullish else "BEAR"
            if (bull_ema and not htf_bullish) or (bear_ema and htf_bullish):
                mtf_aligned = False

    signal = "NEUTRAL ⚪"
    direction = "NONE"
    vol_valid = True if not strict_vol else vol_spike

    if bull_ema and bull_macd and (45 < rsi < 75) and mtf_aligned and vol_valid:
        signal = "LONG 🟢"
        direction = "LONG"
    elif bear_ema and bear_macd and (25 < rsi < 55) and mtf_aligned and vol_valid:
        signal = "SHORT 🔴"
        direction = "SHORT"

    # Risk & Liquidation Controls
    if direction == "LONG":
        entry, sl, tp = price, price - (1.5 * atr), price + (3.0 * atr)
        sl_pct = (entry - sl) / entry
        
        # Zero Liquidation Safety Calculation: Ensure Liquidation is at least 2x distance of SL
        max_safe_leverage = int(0.5 / sl_pct)
        leverage = min(max(max_safe_leverage, 1), 10) # Strictly capped at 10x max
        est_liq_price = entry * (1 - (1 / leverage) * 0.9)
        
        # If SL is worse than Liquidation, REJECT trade for safety
        if sl <= est_liq_price: direction, signal = "NONE", "NEUTRAL ⚪"

    elif direction == "SHORT":
        entry, sl, tp = price, price + (1.5 * atr), price - (3.0 * atr)
        sl_pct = (sl - entry) / entry
        
        max_safe_leverage = int(0.5 / sl_pct)
        leverage = min(max(max_safe_leverage, 1), 10)
        est_liq_price = entry * (1 + (1 / leverage) * 0.9)
        
        if sl >= est_liq_price: direction, signal = "NONE", "NEUTRAL ⚪"

    else:
        entry, sl, tp, leverage, est_liq_price = price, 0.0, 0.0, 1, 0.0

    # Tracking & ETA Calculations
    entry_status = "WAITING"
    time_to_tp_min = 0
    warning_flag = None

    if direction != "NONE":
        tf_mins = {"1m": 1, "5m": 5, "15m": 15}.get(timeframe, 5)
        
        # Calculate distance to TP in candles using volatility
        dist_to_tp = abs(tp - price)
        candles_needed = dist_to_tp / (atr if atr > 0 else price * 0.01)
        time_to_tp_min = int(candles_needed * tf_mins)
        
        # Entry Tracking logic
        if direction == "LONG":
            if price <= entry and price > sl: entry_status = "IN ENTRY ZONE 🎯"
            elif price > entry: entry_status = "RUNNING IN PROFIT 🚀"
            
            # Threat Detector for LONGs
            if last['MACD_Hist'] < prev['MACD_Hist'] or rsi > 72:
                warning_flag = "⚠️ MACD Fading or Overbought! Consider taking profit early."
                
        elif direction == "SHORT":
            if price >= entry and price < sl: entry_status = "IN ENTRY ZONE 🎯"
            elif price < entry: entry_status = "RUNNING IN PROFIT 🚀"
            
            # Threat Detector for SHORTs
            if last['MACD_Hist'] > prev['MACD_Hist'] or rsi < 28:
                warning_flag = "⚠️ MACD Reversing or Oversold! Consider taking profit early."

    return {
        "Coin": coin_name,
        "Signal": signal,
        "Price": price,
        "F_Price": format_price(price),
        "Entry": format_price(entry) if direction != "NONE" else "-",
        "SL": format_price(sl) if direction != "NONE" else "-",
        "TP": format_price(tp) if direction != "NONE" else "-",
        "Liq_Price": format_price(est_liq_price) if direction != "NONE" else "-",
        "Lev": f"{leverage}x",
        "HTF": htf_status,
        "RSI": rsi,
        "Vol": "🔥 High" if vol_spike else "Low",
        "Entry_Status": entry_status,
        "ETA_TP": f"~{time_to_tp_min} mins" if time_to_tp_min > 0 else "-",
        "Warning": warning_flag,
        "Trade_Link": f"https://coindcx.com/futures/B-{coin_name}_USDT",
        "Error": False
    }

# Execution & UI
if selected_coins:
    with st.spinner("Executing quantitative matrix scan..."):
        with ThreadPoolExecutor(max_workers=8) as executor:
            raw_results = list(executor.map(evaluate_signal, selected_coins))
    results = [r for r in raw_results if not r.get("Error")]
    failed = [r["Coin"] for r in raw_results if r.get("Error")]
else:
    results, failed = [], []
    st.info("💡 Select assets in the sidebar to activate the scanner.")

if failed: st.warning(f"⚠️ Could not fetch market data for: {', '.join(failed)}")

if results:
    df = pd.DataFrame(results).drop(columns=["Error"])
    active_longs = len(df[df['Signal'] == "LONG 🟢"])
    active_shorts = len(df[df['Signal'] == "SHORT 🔴"])

    # Dashboard Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Assets Monitored", len(results))
    m2.metric("Active Long Setups", active_longs)
    m3.metric("Active Short Setups", active_shorts)
    m4.metric("Liquidation Guard", "ACTIVE 🛡️")
    st.markdown("<br>", unsafe_allow_html=True)

    # Signal Cards
    active_setups = df[df['Signal'].str.contains("LONG|SHORT")]
    st.markdown("### ⚡ Live Execution Signals & Trade Tracking")
    
    if not active_setups.empty:
        cols = st.columns(min(len(active_setups), 3))
        for i, (_, row) in enumerate(active_setups.iterrows()):
            card_class = "trade-card-long" if "LONG" in row['Signal'] else "trade-card-short"
            val_class = "metric-value-long" if "LONG" in row['Signal'] else "metric-value-short"
            with cols[i % 3]:
                st.markdown(f"""
                <div class="trade-card {card_class}">
                    <div class="card-header">
                        <span>{row['Coin']}-PERP</span>
                        <span class="{val_class}" style="font-size:0.85rem; border:1px solid currentColor; padding:2px 8px; border-radius:12px;">{row['Signal']}</span>
                    </div>
                    <div style="margin-bottom: 8px;"><span class="status-badge">{row['Entry_Status']}</span></div>
                    <div class="card-metric"><span class="metric-label">Current / Entry:</span> <span style="color:#f3f4f6; font-weight:600;">${row['F_Price']}</span></div>
                    <div class="card-metric"><span class="metric-label">Stop Loss (SL):</span> <span style="color:#ef4444;">${row['SL']}</span></div>
                    <div class="card-metric"><span class="metric-label">Take Profit (TP):</span> <span style="color:#10b981;">${row['TP']}</span></div>
                    <div class="card-metric"><span class="metric-label">Est. Liquidation:</span> <span style="color:#f59e0b;">${row['Liq_Price']}</span></div>
                    <div class="card-metric"><span class="metric-label">Safe Leverage:</span> <span style="color:#38bdf8;">{row['Lev']}</span></div>
                    <div class="card-metric"><span class="metric-label">Est. Time to TP:</span> <span style="color:#d1d5db;">{row['ETA_TP']}</span></div>
                    {'<div class="warning-box">' + row['Warning'] + '</div>' if row['Warning'] else ''}
                    <hr style="border:0; height:1px; background:#1f2937; margin:10px 0;">
                    <div>
                        <a href="{row['Trade_Link']}" target="_blank" style="color:#3b82f6; text-decoration:none; font-size:0.85rem; font-weight:600;">↗ Open Chart on CoinDCX</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No active setups meeting strict zero-liquidation & momentum requirements at this moment.")

    st.markdown("---")
    st.markdown("### 📊 Market Overview Matrix")

    display_df = df[['Coin', 'Signal', 'F_Price', 'Entry_Status', 'Lev', 'Liq_Price', 'ETA_TP', 'HTF', 'RSI', 'Vol', 'Trade_Link']].rename(
        columns={"F_Price": "Price", "Entry_Status": "Status", "Liq_Price": "Est. Liq Price", "ETA_TP": "Est. Time"}
    )
    
    def style_dataframe(val):
        if "LONG" in str(val) or "PROFIT" in str(val): return 'color: #10b981; font-weight: 600;'
        if "SHORT" in str(val): return 'color: #ef4444; font-weight: 600;'
        if "ENTRY" in str(val): return 'color: #38bdf8; font-weight: 600;'
        return ''

    st.dataframe(
        display_df.style.map(style_dataframe, subset=['Signal', 'Status']),
        column_config={"Trade_Link": st.column_config.LinkColumn("Action", display_text="Trade ↗")},
        use_container_width=True,
        hide_index=True
    )

if auto_refresh:
    time.sleep(10)
    st.rerun()
