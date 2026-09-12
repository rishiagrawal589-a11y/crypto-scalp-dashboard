import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Page Configuration
st.set_page_config(page_title="CoinDCX Scalp Signals", layout="wide", page_icon="⚡")

st.title("⚡ Pro Crypto Scalp & Trend Signals Dashboard")
st.caption("Real-time momentum, trend, and volume scanner optimized for CoinDCX Perpetual Futures.")

# Sidebar Configuration
st.sidebar.header("⚙️ Scalping Controls")
timeframe = st.sidebar.selectbox("Signal Timeframe", ["1m", "5m", "15m"], index=1)
leverage = st.sidebar.slider("Trading Leverage", 1, 20, 5)
sl_pct = st.sidebar.slider("Stop Loss %", 0.3, 2.0, 0.8) / 100
tp_pct = st.sidebar.slider("Take Profit %", 0.5, 5.0, 1.5) / 100
auto_refresh = st.sidebar.checkbox("Auto Refresh (10s)", value=False)

# Tracked Pairs mapped to CoinDCX Pairs and Direct Trade URLs
COINS = {
    "BTC": {"coindcx": "B-BTC_USDT", "bybit": "BTCUSDT", "url": "https://coindcx.com/futures/BTCUSDT"},
    "ETH": {"coindcx": "B-ETH_USDT", "bybit": "ETHUSDT", "url": "https://coindcx.com/futures/ETHUSDT"},
    "SOL": {"coindcx": "B-SOL_USDT", "bybit": "SOLUSDT", "url": "https://coindcx.com/futures/SOLUSDT"},
    "BNB": {"coindcx": "B-BNB_USDT", "bybit": "BNBUSDT", "url": "https://coindcx.com/futures/BNBUSDT"},
    "XRP": {"coindcx": "B-XRP_USDT", "bybit": "XRPUSDT", "url": "https://coindcx.com/futures/XRPUSDT"},
    "DOGE": {"coindcx": "B-DOGE_USDT", "bybit": "DOGEUSDT", "url": "https://coindcx.com/futures/DOGEUSDT"},
    "ADA": {"coindcx": "B-ADA_USDT", "bybit": "ADAUSDT", "url": "https://coindcx.com/futures/ADAUSDT"},
    "AVAX": {"coindcx": "B-AVAX_USDT", "bybit": "AVAXUSDT", "url": "https://coindcx.com/futures/AVAXUSDT"},
    "NEAR": {"coindcx": "B-NEAR_USDT", "bybit": "NEARUSDT", "url": "https://coindcx.com/futures/NEARUSDT"},
    "LINK": {"coindcx": "B-LINK_USDT", "bybit": "LINKUSDT", "url": "https://coindcx.com/futures/LINKUSDT"}
}

def calculate_indicators(df):
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss.replace(0, 0.00001))
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    return df

def fetch_data(coin_name, config):
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Primary Source: CoinDCX Public Candles API
    try:
        url = f"https://public.coindcx.com/market_data/candles/?pair={config['coindcx']}&interval={timeframe}&limit=50"
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 20:
                df = pd.DataFrame(data).iloc[::-1].reset_index(drop=True)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['volume'].astype(float)
                return calculate_indicators(df), "CoinDCX"
    except Exception:
        pass

    # 2. Secondary Source: Bybit Futures Public API
    try:
        bybit_interval = {"1m": "1", "5m": "5", "15m": "15"}.get(timeframe, "5")
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={config['bybit']}&interval={bybit_interval}&limit=50"
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json().get("result", {}).get("list", [])
            if len(data) > 20:
                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover']).iloc[::-1].reset_index(drop=True)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['volume'].astype(float)
                return calculate_indicators(df), "Bybit"
    except Exception:
        pass

    return None, None

def evaluate_signal(df, coin_name, trade_url):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    rsi = round(last['RSI'], 1) if not np.isnan(last['RSI']) else 50.0
    
    vol_sma = last['Vol_SMA'] if not np.isnan(last['Vol_SMA']) else 1.0
    vol_spike = last['volume'] > (vol_sma * 1.3)
    
    # Trend Analysis
    bullish = last['EMA_9'] > last['EMA_21']
    bearish = last['EMA_9'] < last['EMA_21']
    fresh_crossover = (bullish and prev['EMA_9'] <= prev['EMA_21']) or (bearish and prev['EMA_9'] >= prev['EMA_21'])

    signal = "NEUTRAL ⚪"
    status_type = "info"
    
    if bullish and (50 < rsi < 70):
        if vol_spike or fresh_crossover:
            signal = "STRONG BUY 🟢"
            status_type = "success"
        else:
            signal = "BUY 📈"
            status_type = "success"
    elif bearish and (30 < rsi < 50):
        if vol_spike or fresh_crossover:
            signal = "STRONG SELL 🔴"
            status_type = "error"
        else:
            signal = "SELL 📉"
            status_type = "error"

    # Targets Calculation
    if "BUY" in signal:
        sl_target = price * (1 - sl_pct)
        tp_target = price * (1 + tp_pct)
    elif "SELL" in signal:
        sl_target = price * (1 + sl_pct)
        tp_target = price * (1 - tp_pct)
    else:
        sl_target, tp_target = 0.0, 0.0

    return {
        "Coin": coin_name,
        "Price ($)": round(price, 4),
        "Signal": signal,
        "RSI": rsi,
        "Volume Spike": "YES 🔥" if vol_spike else "NORMAL",
        "Stop Loss ($)": round(sl_target, 4),
        "Take Profit ($)": round(tp_target, 4),
        "Trade": trade_url
    }

def process_item(item):
    coin_name, config = item
    df, source = fetch_data(coin_name, config)
    if df is not None:
        return evaluate_signal(df, coin_name, config['url'])
    return None

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(filter(None, executor.map(process_item, COINS.items())))

# UI Rendering
if len(results) > 0:
    results_df = pd.DataFrame(results)

    # 1. Actionable Hot Alerts Section
    st.subheader("🔥 Actionable Hot Signals")
    hot_signals = results_df[results_df['Signal'].str.contains("STRONG")]

    if not hot_signals.empty:
        cols = st.columns(len(hot_signals))
        for i, (_, row) in enumerate(hot_signals.iterrows()):
            with cols[i]:
                st.metric(label=f"{row['Coin']} ({row['Signal']})", value=f"${row['Price ($)']}", delta=f"RSI: {row['RSI']}")
                st.caption(f"**SL:** ${row['Stop Loss ($)']} | **TP:** ${row['Take Profit ($)']}")
                st.markdown(f"[👉 Trade {row['Coin']} on CoinDCX]({row['Trade']})")
    else:
        st.info("No high-volatility breakout setups detected. Monitor the full matrix below for developing signals.")

    # 2. Main Market Matrix Table
    st.subheader("📊 Live Market Scanner Matrix")

    def highlight_row(val):
        if "STRONG BUY" in val: return 'background-color: #1b4332; color: #52b788; font-weight: bold;'
        if "BUY" in val: return 'background-color: #2d6a4f; color: white;'
        if "STRONG SELL" in val: return 'background-color: #5c061c; color: #ff4d6d; font-weight: bold;'
        if "SELL" in val: return 'background-color: #800f2f; color: white;'
        return ''

    st.dataframe(
        results_df.style.map(highlight_row, subset=['Signal']),
        column_config={
            "Trade": st.column_config.LinkColumn("CoinDCX Direct Link", display_text="Open Chart")
        },
        use_container_width=True
    )
else:
    st.warning("⚠️ Fetching market data... Click Refresh if data takes more than 5 seconds.")

if auto_refresh:
    time.sleep(10)
    st.rerun()
