import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Page Configuration
st.set_page_config(
    page_title="CoinDCX Pro Terminal",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# Custom Institutional Dark-Theme CSS Styling
st.markdown("""
<style>
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #f0f6fc;
        margin-bottom: 2px;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #8b949e;
        margin-bottom: 20px;
    }
    .trade-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .trade-card-long { border-left: 5px solid #238636; }
    .trade-card-short { border-left: 5px solid #da3633; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⚡ CoinDCX Perpetual Quantitative Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Multi-Timeframe Quantitative Momentum Engine & Direct Execution Risk Calculator.</div>', unsafe_allow_html=True)

# Master Presets
PRESET_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "NEAR", "LINK",
    "PEPE", "SHIB", "SUI", "APT", "INJ", "FET", "RENDER", "ARBITRUM", "OP", "TIA"
]

# Initialize Session State Session Watchlist and All Available Options
if "options_list" not in st.session_state:
    st.session_state.options_list = list(PRESET_COINS)

if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["BTC", "ETH", "SOL", "PEPE", "SUI"]

# Callback Functions for Custom Add Buttons
def add_custom_coin_callback():
    coin = st.session_state.custom_input_field.strip().upper()
    if coin:
        if coin not in st.session_state.options_list:
            st.session_state.options_list.append(coin)
        if coin not in st.session_state.watchlist:
            st.session_state.watchlist.append(coin)
        st.session_state.custom_input_field = ""

def add_preset_memes():
    for coin in ["PEPE", "DOGE", "SHIB"]:
        if coin not in st.session_state.options_list:
            st.session_state.options_list.append(coin)
        if coin not in st.session_state.watchlist:
            st.session_state.watchlist.append(coin)

def add_preset_l1s():
    for coin in ["SOL", "AVAX", "SUI", "APT", "NEAR"]:
        if coin not in st.session_state.options_list:
            st.session_state.options_list.append(coin)
        if coin not in st.session_state.watchlist:
            st.session_state.watchlist.append(coin)

# Sidebar Controls
st.sidebar.markdown("### 🎯 Watchlist Controls")

# Custom Coin Text Input
st.sidebar.text_input(
    "Add Unlisted Ticker (e.g. WIF, KAS):", 
    key="custom_input_field",
    on_change=add_custom_coin_callback
)
st.sidebar.button("➕ Add Custom Coin", on_click=add_custom_coin_callback)

# Preset Quick-Add Buttons
st.sidebar.markdown("**Quick Sector Presets:**")
col_p1, col_p2 = st.sidebar.columns(2)
col_p1.button("🔥 Memes", on_click=add_preset_memes)
col_p2.button("🚀 Layer-1s", on_click=add_preset_l1s)

# Multiselect Control linked directly to session_state
selected_coins = st.sidebar.multiselect(
    "Active Coins Scanner List (or type to add):",
    options=st.session_state.options_list,
    key="watchlist",
    accept_new_options=True
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛡️ Risk Parameters")
timeframe = st.sidebar.selectbox("Primary Signal Timeframe", ["1m", "5m", "15m"], index=1)
enable_mtf = st.sidebar.checkbox("Enable Multi-Timeframe Alignment Check", value=True)
auto_refresh = st.sidebar.checkbox("Auto Refresh (Every 10s)", value=False)

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
                return calculate_indicators(df)
    except Exception:
        pass

    # Secondary Backup Source: Bybit API
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
                return calculate_indicators(df)
    except Exception:
        pass

    return None

def evaluate_signal(coin_name):
    df_primary = fetch_data(coin_name, timeframe)
    if df_primary is None or df_primary.empty:
        return None

    last = df_primary.iloc[-1]
    price = last['close']
    rsi = round(last['RSI'], 1) if not np.isnan(last['RSI']) else 50.0
    atr = last['ATR'] if not np.isnan(last['ATR']) else price * 0.01
    
    vol_sma = last['Vol_SMA'] if not np.isnan(last['Vol_SMA']) else 1.0
    vol_spike = last['volume'] > (vol_sma * 1.3)
    
    bullish = last['EMA_9'] > last['EMA_21']
    bearish = last['EMA_9'] < last['EMA_21']

    # Multi-Timeframe Alignment (15m HTF Trend)
    mtf_aligned = True
    htf_status = "N/A"
    if enable_mtf and timeframe != "15m":
        df_htf = fetch_data(coin_name, "15m")
        if df_htf is not None and not df_htf.empty:
            htf_last = df_htf.iloc[-1]
            htf_bullish = htf_last['EMA_9'] > htf_last['EMA_21']
            htf_status = "BULLISH 🟢" if htf_bullish else "BEARISH 🔴"
            if (bullish and not htf_bullish) or (bearish and htf_bullish):
                mtf_aligned = False

    signal = "NEUTRAL ⚪"
    direction = "NONE"
    
    if bullish and (50 < rsi < 70) and mtf_aligned:
        signal = "LONG 🟢"
        direction = "LONG"
    elif bearish and (30 < rsi < 50) and mtf_aligned:
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

    # Direct Trading link format
    trade_url = f"https://coindcx.com/futures/B-{coin_name}_USDT"
    decimals = 6 if price < 1 else 4

    return {
        "Coin": coin_name,
        "Signal": signal,
        "Price ($)": round(price, decimals),
        "Entry Zone ($)": round(entry_price, decimals),
        "Stop Loss ($)": round(sl_price, decimals),
        "Take Profit ($)": round(tp_price, decimals),
        "Rec. Leverage": f"{rec_leverage}x",
        "Risk-Reward": f"1:{rrr}",
        "15m HTF Trend": htf_status,
        "RSI": rsi,
        "Vol Spike": "YES 🔥" if vol_spike else "NORMAL",
        "Trade": trade_url
    }

if selected_coins:
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(filter(None, executor.map(evaluate_signal, selected_coins)))
else:
    results = []
    st.info("💡 Select or add coins in the sidebar to activate the quantitative scanner.")

if len(results) > 0:
    results_df = pd.DataFrame(results)

    # Active Execution Signal Cards
    st.markdown("### 🔥 High-Confidence Scalp Setups")
    active_setups = results_df[results_df['Signal'].str.contains("LONG|SHORT")]

    if not active_setups.empty:
        cols = st.columns(min(len(active_setups), 3))
        for i, (_, row) in enumerate(active_setups.iterrows()):
            card_class = "trade-card-long" if "LONG" in row['Signal'] else "trade-card-short"
            with cols[i % 3]:
                st.markdown(f"""
                <div class="trade-card {card_class}">
                    <h4 style="margin:0; color:#f0f6fc;">{row['Coin']} Perpetual — <span style="font-size:0.9em;">{row['Signal']}</span></h4>
                    <hr style="border-color:#30363d; margin: 10px 0;">
                    <p style="margin:4px 0;">📍 <b>Entry Zone:</b> ${row['Entry Zone ($)']}</p>
                    <p style="margin:4px 0;">🛑 <b>Stop Loss:</b> ${row['Stop Loss ($)']}</p>
                    <p style="margin:4px 0;">🎯 <b>Take Profit:</b> ${row['Take Profit ($)']}</p>
                    <p style="margin:4px 0;">⚡ <b>Rec. Leverage:</b> {row['Rec. Leverage']} | <b>RRR:</b> {row['Risk-Reward']}</p>
                    <p style="margin:4px 0;">📊 <b>RSI:</b> {row['RSI']} | <b>15m Trend:</b> {row['15m HTF Trend']}</p>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(f"[📈 Open {row['Coin']} Chart on CoinDCX]({row['Trade']})")
    else:
        st.info("No active multi-timeframe aligned setups detected right now across selected coins.")

    st.markdown("---")

    # Scanner Table Matrix
    st.markdown("### 📊 Market Overview Matrix")

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
