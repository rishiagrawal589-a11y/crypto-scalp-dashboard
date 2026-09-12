import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Page Setup
st.set_page_config(page_title="CoinDCX Scalp Engine & Custom Watchlist", layout="wide", page_icon="⚡")

st.title("⚡ CoinDCX Precision Scalp Engine")
st.caption("Scans real-time market structure with dynamic coin selection to generate exact Entry, SL, TP, and Leverage.")

# Master list of preset popular coins across sectors
PRESET_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "NEAR", "LINK",
    "PEPE", "SHIB", "SUI", "APT", "INJ", "FET", "RENDER", "ARBITRUM", "OP", "TIA"
]

# Sidebar Controls
st.sidebar.header("🎯 Coin Watchlist Selection")

# 1. Custom Text Input for unlisted coins
custom_text_input = st.sidebar.text_input("Add Unlisted Ticker (e.g., WIF, KAS):", value="").strip().upper()

# 2. Dynamic Multiselect Dropdown
default_selected = ["BTC", "ETH", "SOL", "PEPE", "SUI"]
if custom_text_input and custom_text_input not in PRESET_COINS:
    PRESET_COINS.insert(0, custom_text_input)
    default_selected.insert(0, custom_text_input)

selected_coins = st.sidebar.multiselect(
    "Active Scanner Watchlist:",
    options=PRESET_COINS,
    default=default_selected
)

# 3. Quick Sector Presets
st.sidebar.markdown("**Quick Preset Buttons:**")
col_p1, col_p2 = st.sidebar.columns(2)
if col_p1.button("🔥 Memes"):
    selected_coins = list(set(selected_coins + ["PEPE", "DOGE", "SHIB"]))
if col_p2.button("🚀 Layer-1s"):
    selected_coins = list(set(selected_coins + ["SOL", "AVAX", "SUI", "APT", "NEAR"]))

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Risk Controls")
timeframe = st.sidebar.selectbox("Signal Timeframe", ["1m", "5m", "15m"], index=1)
max_risk_pct = st.sidebar.slider("Max Risk % per Trade", 0.5, 3.0, 1.0) / 100
auto_refresh = st.sidebar.checkbox("Auto Refresh (10s)", value=False)

def calculate_indicators(df):
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    # RSI Calculation
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss.replace(0, 0.00001))
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Average True Range (ATR)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['ATR'] = np.max(ranges, axis=1).rolling(14).mean()

    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    return df

def fetch_data(coin_symbol, tf):
    headers = {"User-Agent": "Mozilla/5.0"}
    coindcx_pair = f"B-{coin_symbol}_USDT"
    bybit_symbol = f"{coin_symbol}USDT"
    
    # Primary Source: CoinDCX Futures
    try:
        url = f"https://public.coindcx.com/market_data/candles/?pair={coindcx_pair}&interval={tf}&limit=50"
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 20:
                df = pd.DataFrame(data).iloc[::-1].reset_index(drop=True)
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                return calculate_indicators(df), "CoinDCX"
    except Exception:
        pass

    # Backup Source: Bybit API
    try:
        bybit_interval = {"1m": "1", "5m": "5", "15m": "15"}.get(tf, "5")
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={bybit_symbol}&interval={bybit_interval}&limit=50"
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json().get("result", {}).get("list", [])
            if len(data) > 20:
                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover']).iloc[::-1].reset_index(drop=True)
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                return calculate_indicators(df), "Bybit"
    except Exception:
        pass

    return None, None

def evaluate_signal(df, coin_name):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    rsi = round(last['RSI'], 1) if not np.isnan(last['RSI']) else 50.0
    atr = last['ATR'] if not np.isnan(last['ATR']) else price * 0.01
    
    vol_sma = last['Vol_SMA'] if not np.isnan(last['Vol_SMA']) else 1.0
    vol_spike = last['volume'] > (vol_sma * 1.3)
    
    bullish = last['EMA_9'] > last['EMA_21']
    bearish = last['EMA_9'] < last['EMA_21']

    signal = "NEUTRAL ⚪"
    direction = "NONE"
    
    if bullish and (50 < rsi < 70):
        signal = "LONG 🟢"
        direction = "LONG"
    elif bearish and (30 < rsi < 50):
        signal = "SHORT 🔴"
        direction = "SHORT"

    if direction == "LONG":
        entry_price = price
        sl_price = price - (1.5 * atr)
        tp_price = price + (3.0 * atr)
        sl_distance_pct = (entry_price - sl_price) / entry_price
        rec_leverage = int(min(max(1.0 / (sl_distance_pct * 2.0), 2.0), 20.0))
        rrr = round((tp_price - entry_price) / (entry_price - sl_price), 2)
    elif direction == "SHORT":
        entry_price = price
        sl_price = price + (1.5 * atr)
        tp_price = price - (3.0 * atr)
        sl_distance_pct = (sl_price - entry_price) / entry_price
        rec_leverage = int(min(max(1.0 / (sl_distance_pct * 2.0), 2.0), 20.0))
        rrr = round((entry_price - tp_price) / (sl_price - entry_price), 2)
    else:
        entry_price, sl_price, tp_price, rec_leverage, rrr = price, 0.0, 0.0, 1, 0.0

    trade_url = f"https://coindcx.com/futures/{coin_name}USDT"
    decimals = 6 if price < 1 else 4

    return {
        "Coin": coin_name,
        "Signal": signal,
        "Entry Zone ($)": round(entry_price, decimals),
        "Stop Loss ($)": round(sl_price, decimals),
        "Take Profit ($)": round(tp_price, decimals),
        "Rec. Leverage": f"{rec_leverage}x",
        "Risk-Reward": f"1:{rrr}",
        "RSI": rsi,
        "Vol Spike": "YES 🔥" if vol_spike else "NORMAL",
        "Trade": trade_url
    }

def process_item(coin_name):
    df, source = fetch_data(coin_name, timeframe)
    if df is not None:
        return evaluate_signal(df, coin_name)
    return None

if selected_coins:
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(filter(None, executor.map(process_item, selected_coins)))
else:
    results = []
    st.info("💡 Please select at least one coin from the sidebar selection box.")

if len(results) > 0:
    results_df = pd.DataFrame(results)

    # Active Execution Cards
    st.subheader(f"🔥 Active Scalp Targets ({len(results_df[results_df['Signal'].str.contains('LONG|SHORT')])} Signals)")
    active_setups = results_df[results_df['Signal'].str.contains("LONG|SHORT")]

    if not active_setups.empty:
        cols = st.columns(min(len(active_setups), 3))
        for i, (_, row) in enumerate(active_setups.iterrows()):
            with cols[i % 3]:
                st.subheader(f"{row['Coin']} | {row['Signal']}")
                st.write(f"📍 **Entry Zone:** `${row['Entry Zone ($)']}`")
                st.write(f"🛑 **Stop Loss:** `${row['Stop Loss ($)']}`")
                st.write(f"🎯 **Take Profit:** `${row['Take Profit ($)']}`")
                st.write(f"⚡ **Rec. Leverage:** `{row['Rec. Leverage']}` | **RRR:** `{row['Risk-Reward']}`")
                st.markdown(f"[👉 Execute Trade on CoinDCX]({row['Trade']})")
    else:
        st.info("No active setups matching risk-reward criteria across selected coins right now.")

    # Scanner Table
    st.subheader("📊 Active Selected Watchlist Matrix")

    def highlight_row(val):
        if "LONG" in val: return 'background-color: #1b4332; color: #52b788; font-weight: bold;'
        if "SHORT" in val: return 'background-color: #5c061c; color: #ff4d6d; font-weight: bold;'
        return ''

    st.dataframe(
        results_df.style.map(highlight_row, subset=['Signal']),
        column_config={
            "Trade": st.column_config.LinkColumn("CoinDCX Direct Link", display_text="Open Chart")
        },
        use_container_width=True
    )

if auto_refresh:
    time.sleep(10)
    st.rerun()
