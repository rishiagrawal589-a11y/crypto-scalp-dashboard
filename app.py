import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Page Configuration
st.set_page_config(
    page_title="CoinDCX Pro Quant",
    layout="wide",
    page_icon="💠",
    initial_sidebar_state="expanded"
)

# Professional Institutional UI
st.markdown("""
<style>
    .stApp { background-color: #0b0e14; color: #d1d5db; font-family: 'Inter', sans-serif; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; margin-bottom: 0px; }
    .sub-title { font-size: 0.95rem; color: #9ca3af; margin-bottom: 25px; border-bottom: 1px solid #1f2937; padding-bottom: 15px; }
    .trade-card { background: linear-gradient(145deg, #111827 0%, #0d1117 100%); border: 1px solid #1f2937; border-radius: 10px; padding: 18px; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }
    .trade-card-long { border-top: 4px solid #10b981; }
    .trade-card-short { border-top: 4px solid #ef4444; }
    .card-header { font-size: 1.2rem; font-weight: 700; color: #f3f4f6; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;}
    .card-metric { display: flex; justify-content: space-between; margin: 5px 0; font-size: 0.88rem; color: #d1d5db; }
    .metric-label { color: #9ca3af; font-weight: 500; }
    .warning-box { background-color: #451a03; border: 1px solid #b45309; color: #fde68a; padding: 8px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; margin-top: 10px; }
    .status-badge { background: #1e293b; color: #38bdf8; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">💠 Institutional Momentum Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Multi-Timeframe Macro Alignment (4H/1D) • Zero-Liquidation Engine • Persistent Memory</div>', unsafe_allow_html=True)

# Normalization Map
SYMBOL_MAP = {
    "ARBITRUM": "ARB", "SHIBA": "SHIB", "SHIBAINU": "SHIB", "DOGECOIN": "DOGE",
    "MATIC": "POL", "RIPPLE": "XRP", "SOLANA": "SOL", "CARDANO": "ADA", "AVALANCHE": "AVAX", "POLKADOT": "DOT"
}

def normalize_ticker(raw_input):
    cleaned = raw_input.strip().upper().replace("USDT", "").replace("B-", "")
    return SYMBOL_MAP.get(cleaned, cleaned)

# Persistent Session State (Fixes the disappearing custom coins bug)
if "master_coin_list" not in st.session_state:
    st.session_state.master_coin_list = [
        "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "NEAR", "LINK",
        "PEPE", "SHIB", "WIF", "BONK", "FLOKI", "SUI", "APT", "INJ", "FET", "RENDER",
        "ARB", "OP", "TIA", "SEI", "STX", "FIL", "LTC", "BCH", "POL", "GALA",
        "LDO", "RUNE", "ATOM", "ETC", "ICP", "DOT", "UNI", "AAVE", "SAND", "MANA", 
        "KAS", "TRX", "VET", "ALGO", "DYDX", "CRV", "SNX", "MASK", "GMX", "MAGIC"
    ]

if "active_watchlist" not in st.session_state:
    st.session_state.active_watchlist = ["BTC", "ETH", "SOL", "PEPE", "SUI", "ARB", "WIF"]

# Callbacks
def add_from_dropdown_callback():
    normalized = normalize_ticker(st.session_state.coin_dropdown_selection)
    if normalized and normalized not in st.session_state.active_watchlist:
        st.session_state.active_watchlist.append(normalized)

def add_from_manual_callback():
    if st.session_state.manual_text_input:
        normalized = normalize_ticker(st.session_state.manual_text_input)
        if normalized not in st.session_state.master_coin_list:
            st.session_state.master_coin_list.insert(0, normalized)
        if normalized not in st.session_state.active_watchlist:
            st.session_state.active_watchlist.append(normalized)
        st.session_state.manual_text_input = ""

def add_preset_memes():
    for c in ["PEPE", "DOGE", "SHIB", "WIF", "BONK"]:
        if c not in st.session_state.active_watchlist: st.session_state.active_watchlist.append(c)

def add_preset_l1s():
    for c in ["SOL", "AVAX", "SUI", "APT", "NEAR", "SEI"]:
        if c not in st.session_state.active_watchlist: st.session_state.active_watchlist.append(c)

# Sidebar UI
st.sidebar.markdown("### 🔄 Control Panel")
if st.sidebar.button("⚡ Refresh Data Now", use_container_width=True, type="primary"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Asset Directory")
st.sidebar.selectbox("Select Asset from Directory:", options=st.session_state.master_coin_list, key="coin_dropdown_selection")
st.sidebar.button("➕ Add Selected Asset", on_click=add_from_dropdown_callback, use_container_width=True)

st.sidebar.text_input("Or Input Custom Ticker (e.g. ONDO):", key="manual_text_input", on_change=add_from_manual_callback)
st.sidebar.button("➕ Add Custom Asset", on_click=add_from_manual_callback, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Portfolio Sectors:**")
col_p1, col_p2 = st.sidebar.columns(2)
col_p1.button("🔥 Memes", on_click=add_preset_memes, use_container_width=True)
col_p2.button("🚀 L1s/L2s", on_click=add_preset_l1s, use_container_width=True)

st.sidebar.markdown("---")
selected_coins = st.sidebar.multiselect(
    "Active Scanning Matrix:",
    options=list(dict.fromkeys(st.session_state.master_coin_list + st.session_state.active_watchlist)),
    default=st.session_state.active_watchlist,
    key="active_watchlist"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Quant Parameters")
timeframe = st.sidebar.selectbox("Primary Scalp Resolution", ["1m", "5m", "15m"], index=1)
strict_vol = st.sidebar.checkbox("Require Volume Spike (Strict)", value=True)
auto_refresh = st.sidebar.checkbox("Live Auto-Refresh (15s)", value=False)

def calculate_indicators(df):
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.00001))))
    
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    df['ATR'] = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1).rolling(14).mean()
    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    return df

def fetch_data(coin_symbol, tf):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://public.coindcx.com/market_data/candles/?pair=B-{coin_symbol}_USDT&interval={tf}&limit=60"
        res = requests.get(url, headers=headers, timeout=2)
        if res.status_code == 200 and isinstance(res.json(), list) and len(res.json()) > 20:
            df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
            return calculate_indicators(df)
    except: pass
    
    try:
        bybit_tf = {"1m": "1", "5m": "5", "15m": "15", "4h": "240", "1d": "D"}.get(tf, "5")
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={coin_symbol}USDT&interval={bybit_tf}&limit=60"
        res = requests.get(url, headers=headers, timeout=2)
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
    # Primary Scalp TF
    df = fetch_data(coin_name, timeframe)
    if df is None or df.empty: return {"Coin": coin_name, "Error": True}

    # Macro TFs (4H and 1D)
    df_4h = fetch_data(coin_name, "4h")
    df_1d = fetch_data(coin_name, "1d")
    
    macro_trend = "Neutral ⚪"
    if df_4h is not None and df_1d is not None and not df_4h.empty and not df_1d.empty:
        c_4h, c_1d = df_4h.iloc[-1], df_1d.iloc[-1]
        bull_4h = c_4h['EMA_9'] > c_4h['EMA_21']
        bull_1d = c_1d['EMA_9'] > c_1d['EMA_21']
        
        if bull_4h and bull_1d: macro_trend = "Strong Bull 🟢"
        elif not bull_4h and not bull_1d: macro_trend = "Strong Bear 🔴"
        elif bull_4h and not bull_1d: macro_trend = "Weak Bull (4H) 🟡"
        elif not bull_4h and bull_1d: macro_trend = "Weak Bear (4H) 🟡"

    last, prev = df.iloc[-1], df.iloc[-2]
    price, atr = last['close'], last['ATR'] if not np.isnan(last['ATR']) else last['close'] * 0.01
    rsi = round(last['RSI'], 1) if not np.isnan(last['RSI']) else 50.0
    vol_spike = last['volume'] > (last['Vol_SMA'] * 1.3)
    
    bull_ema, bull_macd = last['EMA_9'] > last['EMA_21'], last['MACD_Hist'] > 0
    bear_ema, bear_macd = last['EMA_9'] < last['EMA_21'], last['MACD_Hist'] < 0

    signal, direction = "NEUTRAL ⚪", "NONE"
    vol_valid = True if not strict_vol else vol_spike

    # Alignment Rules: Do not allow Scalp Longs if Macro is Strong Bear
    if bull_ema and bull_macd and (45 < rsi < 75) and vol_valid and "Strong Bear" not in macro_trend:
        signal, direction = "LONG 🟢", "LONG"
    elif bear_ema and bear_macd and (25 < rsi < 55) and vol_valid and "Strong Bull" not in macro_trend:
        signal, direction = "SHORT 🔴", "SHORT"

    if direction == "LONG":
        entry, sl, tp = price, price - (1.5 * atr), price + (3.0 * atr)
        leverage = min(max(int(0.5 / ((entry - sl) / entry)), 1), 10)
        est_liq_price = entry * (1 - (1 / leverage) * 0.9)
        if sl <= est_liq_price: direction, signal = "NONE", "NEUTRAL ⚪"
    elif direction == "SHORT":
        entry, sl, tp = price, price + (1.5 * atr), price - (3.0 * atr)
        leverage = min(max(int(0.5 / ((sl - entry) / entry)), 1), 10)
        est_liq_price = entry * (1 + (1 / leverage) * 0.9)
        if sl >= est_liq_price: direction, signal = "NONE", "NEUTRAL ⚪"
    else:
        entry, sl, tp, leverage, est_liq_price = price, 0.0, 0.0, 1, 0.0

    entry_status, time_to_tp_min, warning_flag = "WAITING", 0, None

    if direction != "NONE":
        tf_mins = {"1m": 1, "5m": 5, "15m": 15}.get(timeframe, 5)
        time_to_tp_min = int((abs(tp - price) / atr) * tf_mins) if atr > 0 else 0
        
        if direction == "LONG":
            if sl < price <= entry: entry_status = "IN ENTRY ZONE 🎯"
            elif price > entry: entry_status = "RUNNING IN PROFIT 🚀"
            if last['MACD_Hist'] < prev['MACD_Hist'] or rsi > 72:
                warning_flag = "⚠️ Momentum Fading! Move SL to breakeven or close early."
                
        elif direction == "SHORT":
            if sl > price >= entry: entry_status = "IN ENTRY ZONE 🎯"
            elif price < entry: entry_status = "RUNNING IN PROFIT 🚀"
            if last['MACD_Hist'] > prev['MACD_Hist'] or rsi < 28:
                warning_flag = "⚠️ Momentum Reversing! Move SL to breakeven or close early."

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
        "Macro": macro_trend,
        "Entry_Status": entry_status,
        "ETA_TP": f"~{time_to_tp_min} mins" if time_to_tp_min > 0 else "-",
        "Warning": warning_flag,
        "Trade_Link": f"https://pro.coindcx.com/trade/futures/B-{coin_name}_USDT",
        "Error": False
    }

# Main Execution
if selected_coins:
    with st.spinner("Analyzing High & Low Timeframes..."):
        with ThreadPoolExecutor(max_workers=8) as executor:
            raw_results = list(executor.map(evaluate_signal, selected_coins))
    results = [r for r in raw_results if not r.get("Error")]
    failed = [r["Coin"] for r in raw_results if r.get("Error")]
else:
    results, failed = [], []
    st.info("💡 Select assets to build your matrix.")

if failed: st.warning(f"⚠️ Could not fetch market data for: {', '.join(failed)}")

if results:
    df = pd.DataFrame(results).drop(columns=["Error"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Assets Monitored", len(results))
    m2.metric("Active Long Setups", len(df[df['Signal'] == "LONG 🟢"]))
    m3.metric("Active Short Setups", len(df[df['Signal'] == "SHORT 🔴"]))
    m4.metric("Macro Alignment", "ACTIVE 🛡️")
    st.markdown("<br>", unsafe_allow_html=True)

    active_setups = df[df['Signal'].str.contains("LONG|SHORT")]
    st.markdown("### ⚡ Validated Execution Setups")
    
    if not active_setups.empty:
        cols = st.columns(min(len(active_setups), 3))
        for i, (_, row) in enumerate(active_setups.iterrows()):
            card_class = "trade-card-long" if "LONG" in row['Signal'] else "trade-card-short"
            with cols[i % 3]:
                st.markdown(f"""
                <div class="trade-card {card_class}">
                    <div class="card-header">
                        <span>{row['Coin']}-PERP</span>
                        <span style="font-size:0.85rem; border:1px solid currentColor; padding:2px 8px; border-radius:12px;">{row['Signal']}</span>
                    </div>
                    <div style="margin-bottom: 8px;"><span class="status-badge">{row['Entry_Status']}</span></div>
                    <div class="card-metric"><span class="metric-label">Macro 4H/1D Trend:</span> <span style="color:#f3f4f6;">{row['Macro']}</span></div>
                    <div class="card-metric"><span class="metric-label">Current / Entry:</span> <span style="color:#f3f4f6; font-weight:600;">${row['F_Price']}</span></div>
                    <div class="card-metric"><span class="metric-label">Stop Loss (SL):</span> <span style="color:#ef4444;">${row['SL']}</span></div>
                    <div class="card-metric"><span class="metric-label">Take Profit (TP):</span> <span style="color:#10b981;">${row['TP']}</span></div>
                    <div class="card-metric"><span class="metric-label">Est. Liquidation:</span> <span style="color:#f59e0b;">${row['Liq_Price']}</span></div>
                    <div class="card-metric"><span class="metric-label">Safe Leverage:</span> <span style="color:#38bdf8;">{row['Lev']}</span></div>
                    {'<div class="warning-box">' + row['Warning'] + '</div>' if row['Warning'] else ''}
                    <hr style="border:0; height:1px; background:#1f2937; margin:10px 0;">
                    <div><a href="{row['Trade_Link']}" target="_blank" style="color:#3b82f6; text-decoration:none; font-weight:600;">↗ Open Chart on CoinDCX</a></div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No active setups meeting Macro Alignment & strict criteria right now.")

    st.markdown("---")
    st.markdown("### 📊 Complete Quant Matrix")
    display_df = df[['Coin', 'Signal', 'Macro', 'F_Price', 'Entry_Status', 'Lev', 'Trade_Link']].rename(
        columns={"F_Price": "Price", "Entry_Status": "Status"}
    )
    def style_dataframe(val):
        if "LONG" in str(val) or "Bull" in str(val): return 'color: #10b981; font-weight: 600;'
        if "SHORT" in str(val) or "Bear" in str(val): return 'color: #ef4444; font-weight: 600;'
        return ''

    st.dataframe(
        display_df.style.map(style_dataframe, subset=['Signal', 'Macro']),
        column_config={"Trade_Link": st.column_config.LinkColumn("Action", display_text="Trade ↗")},
        use_container_width=True, hide_index=True
    )

if auto_refresh:
    time.sleep(15)
    st.rerun()
