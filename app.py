import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

# Configure Web App Layout
st.set_page_config(page_title="Crypto Scalp Signal Dashboard", layout="wide", page_icon="⚡")

st.title("⚡ Live Crypto Scalping & Trend Signal Dashboard")
st.caption("Scans real-time futures market data to identify scalp entries with exact SL & TP target prices.")

# User Sidebar Options
st.sidebar.header("⚙️ Scalp Settings")
timeframe = st.sidebar.selectbox("Select Timeframe", ["1m", "5m", "15m"], index=1)
leverage = st.sidebar.slider("Leverage (for target calculations)", 1, 20, 5)
sl_pct = st.sidebar.slider("Stop Loss %", 0.3, 2.0, 0.8) / 100
tp_pct = st.sidebar.slider("Take Profit %", 0.5, 5.0, 1.5) / 100
auto_refresh = st.sidebar.checkbox("Auto Refresh (Every 10s)", value=False)

# List of top liquid futures coins to scan
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "NEARUSDT", "LINKUSDT"]

# Technical Indicator Calculations
def calculate_indicators(df):
    # Exponential Moving Averages
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
    
    # RSI (Relative Strength Index)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Volume Average
    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    return df

# Fetch Live Binance Market Data
def fetch_klines(symbol, interval):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=50"
    try:
        res = requests.get(url, timeout=5).json()
        df = pd.DataFrame(res, columns=['time', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return calculate_indicators(df)
    except Exception:
        return None

# Generate Trade Signal Logic
def get_signal(df, symbol):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    rsi = last['RSI']
    
    # Check Conditions
    ema_bullish = last['EMA_9'] > last['EMA_21'] and prev['EMA_9'] <= prev['EMA_21']
    ema_bearish = last['EMA_9'] < last['EMA_21'] and prev['EMA_9'] >= prev['EMA_21']
    vol_spike = last['volume'] > (last['Vol_SMA'] * 1.3)
    
    signal = "NEUTRAL"
    confidence = "LOW"
    
    if (last['EMA_9'] > last['EMA_21']) and (rsi > 50) and (rsi < 70):
        signal = "STRONG BUY" if vol_spike else "BUY"
        confidence = "HIGH" if vol_spike else "MEDIUM"
    elif (last['EMA_9'] < last['EMA_21']) and (rsi < 50) and (rsi > 30):
        signal = "STRONG SELL" if vol_spike else "SELL"
        confidence = "HIGH" if vol_spike else "MEDIUM"

    # SL / TP Price Calculations
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

# Main Execution & Table Rendering
results = []
for coin in COINS:
    df = fetch_klines(coin, timeframe)
    if df is not None and not df.empty:
        results.append(get_signal(df, coin))

results_df = pd.DataFrame(results)

# Display Top Cards for Quick Scalp Alerts
st.subheader("🚀 High-Confidence Scalp Alerts")
strong_signals = results_df[results_df['Signal'].isin(["STRONG BUY", "STRONG SELL"])]

if not strong_signals.empty:
    cols = st.columns(len(strong_signals))
    for i, (_, row) in enumerate(strong_signals.iterrows()):
        color = "green" if "BUY" in row['Signal'] else "red"
        cols[i].metric(
            label=f"{row['Coin']} ({row['Signal']})",
            value=f"${row['Price ($)']}",
            delta=f"RSI: {row['RSI']} | Vol: {row['Vol Spike']}"
        )
else:
    st.info("No High-Confidence (Volume Spike) setups detected right now. Watch the live matrix below.")

# Render Complete Market Matrix Table
st.subheader("📊 All Coins Live Matrix")

def color_signals(val):
    if "STRONG BUY" in val: return 'background-color: #1b4332; color: #52b788; font-weight: bold;'
    if "BUY" in val: return 'background-color: #2d6a4f; color: white;'
    if "STRONG SELL" in val: return 'background-color: #5c061c; color: #ff4d6d; font-weight: bold;'
    if "SELL" in val: return 'background-color: #800f2f; color: white;'
    return ''

st.dataframe(results_df.style.map(color_signals, subset=['Signal']), use_container_width=True)

# Auto Refresh loop option
if auto_refresh:
    time.sleep(10)
    st.rerun()
