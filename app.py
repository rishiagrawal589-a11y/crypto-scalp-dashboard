import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="CoinDCX Futures Scalp Dashboard", layout="wide", page_icon="⚡")

st.title("⚡ Live CoinDCX Scalping & Trend Signal Dashboard")
st.caption("Scans real-time CoinDCX futures market data to identify scalp entries with exact SL & TP target prices.")

# User Sidebar Options
st.sidebar.header("⚙️ Scalp Settings")
timeframe = st.sidebar.selectbox("Select Timeframe", ["1m", "5m", "15m"], index=1)
leverage = st.sidebar.slider("Leverage (for target calculations)", 1, 20, 5)
sl_pct = st.sidebar.slider("Stop Loss %", 0.3, 2.0, 0.8) / 100
tp_pct = st.sidebar.slider("Take Profit %", 0.5, 5.0, 1.5) / 100
auto_refresh = st.sidebar.checkbox("Auto Refresh (Every 10s)", value=False)

# CoinDCX Futures Pairs (B- prefix indicates Binance liquidity pool used by CoinDCX)
COINDCX_PAIRS = {
    "BTCUSDT": "B-BTC_USDT",
    "ETHUSDT": "B-ETH_USDT",
    "SOLUSDT": "B-SOL_USDT",
    "BNBUSDT": "B-BNB_USDT",
    "XRPUSDT": "B-XRP_USDT",
    "DOGEUSDT": "B-DOGE_USDT",
    "ADAUSDT": "B-ADA_USDT",
    "AVAXUSDT": "B-AVAX_USDT",
    "NEARUSDT": "B-NEAR_USDT",
    "LINKUSDT": "B-LINK_USDT"
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

def fetch_coindcx_klines(symbol_name, coindcx_pair, interval):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = f"https://public.coindcx.com/market_data/candles/?pair={coindcx_pair}&interval={interval}&limit=50"
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                # CoinDCX returns data ordered from newest to oldest
                df = pd.DataFrame(data)
                df = df.iloc[::-1].reset_index(drop=True)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['volume'].astype(float)
                return calculate_indicators(df)
    except Exception:
        pass

    return None

def get_signal(df, symbol):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    rsi = last['RSI'] if not np.isnan(last['RSI']) else 50.0
    
    vol_sma = last['Vol_SMA'] if not np.isnan(last['Vol_SMA']) else 1.0
    vol_spike = last['volume'] > (vol_sma * 1.3)
    
    signal = "NEUTRAL"
    confidence = "LOW"
    
    if (last['EMA_9'] > last['EMA_21']) and (rsi > 50) and (rsi < 70):
        signal = "STRONG BUY" if vol_spike else "BUY"
        confidence = "HIGH" if vol_spike else "MEDIUM"
    elif (last['EMA_9'] < last['EMA_21']) and (rsi < 50) and (rsi > 30):
        signal = "STRONG SELL" if vol_spike else "SELL"
        confidence = "HIGH" if vol_spike else "MEDIUM"

    if "BUY" in signal:
        sl_price = price * (1 - sl_pct)
        tp_price = price * (1 + tp_pct)
    elif "SELL" in signal:
        sl_price = price * (1 + sl_pct)
        tp_price = price * (1 - tp_pct)
    else:
        sl_price, tp_price = 0.0, 0.0

    return {
        "Coin": symbol,
        "Price ($)": round(price, 4),
        "Signal": signal,
        "Confidence": confidence,
        "RSI": round(rsi, 1),
        "Vol Spike": "YES 🔥" if vol_spike else "NO",
        "SL Target ($)": round(sl_price, 4),
        "TP Target ($)": round(tp_price, 4)
    }

def process_pair(item):
    symbol_name, coindcx_pair = item
    df = fetch_coindcx_klines(symbol_name, coindcx_pair, timeframe)
    if df is not None and not df.empty and len(df) > 20:
        return get_signal(df, symbol_name)
    return None

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(filter(None, executor.map(process_pair, COINDCX_PAIRS.items())))

if len(results) > 0:
    results_df = pd.DataFrame(results)

    st.subheader("🚀 High-Confidence Scalp Alerts")
    if 'Signal' in results_df.columns:
        strong_signals = results_df[results_df['Signal'].isin(["STRONG BUY", "STRONG SELL"])]

        if not strong_signals.empty:
            cols = st.columns(len(strong_signals))
            for i, (_, row) in enumerate(strong_signals.iterrows()):
                cols[i].metric(
                    label=f"{row['Coin']} ({row['Signal']})",
                    value=f"${row['Price ($)']}",
                    delta=f"RSI: {row['RSI']} | Vol: {row['Vol Spike']}"
                )
        else:
            st.info("No High-Confidence (Volume Spike) setups detected right now. Watch the live matrix below.")

    st.subheader("📊 All Coins Live Matrix")

    def color_signals(val):
        if "STRONG BUY" in val: return 'background-color: #1b4332; color: #52b788; font-weight: bold;'
        if "BUY" in val: return 'background-color: #2d6a4f; color: white;'
        if "STRONG SELL" in val: return 'background-color: #5c061c; color: #ff4d6d; font-weight: bold;'
        if "SELL" in val: return 'background-color: #800f2f; color: white;'
        return ''

    st.dataframe(results_df.style.map(color_signals, subset=['Signal']), use_container_width=True)

else:
    st.warning("⚠️ Connecting to CoinDCX servers... Click 'Refresh' or toggle Auto Refresh in the sidebar.")

if auto_refresh:
    time.sleep(10)
    st.rerun()
