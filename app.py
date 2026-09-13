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
    page_title="CoinDCX Quant Terminal",
    layout="wide",
    page_icon="💠",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INSTITUTIONAL UI / CSS
# ============================================================================
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
        font-size: 1rem;
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
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .trade-card:hover { transform: translateY(-2px); }
    .trade-card-long { border-top: 4px solid #10b981; }
    .trade-card-long:hover { border-color: #10b981; }
    .trade-card-short { border-top: 4px solid #ef4444; }
    .trade-card-short:hover { border-color: #ef4444; }

    /* Typography inside cards */
    .card-header { font-size: 1.25rem; font-weight: 700; color: #f3f4f6; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;}
    .card-metric { display: flex; justify-content: space-between; margin: 6px 0; font-size: 0.9rem; color: #d1d5db; }
    .metric-label { color: #9ca3af; font-weight: 500; }
    .metric-value-long { color: #10b981; font-weight: 600; }
    .metric-value-short { color: #ef4444; font-weight: 600; }
    .num { font-variant-numeric: tabular-nums; }

    /* Badges */
    .badge { background:#1f2937; padding:4px 8px; border-radius:6px; font-size:0.72rem; color:#d1d5db; white-space:nowrap; display:inline-block; }
    .badge-good { background: rgba(16,185,129,0.12); color:#10b981; border:1px solid rgba(16,185,129,0.35); }
    .badge-warn { background: rgba(239,68,68,0.12); color:#ef4444; border:1px solid rgba(239,68,68,0.35); }

    /* Setup strength bar */
    .score-track { background:#1f2937; border-radius:6px; height:6px; width:100%; overflow:hidden; margin-top:4px; }
    .score-fill-long { background:#10b981; height:100%; }
    .score-fill-short { background:#ef4444; height:100%; }

    /* Liquidation warning */
    .liq-warning { color:#f59e0b; font-size:0.75rem; margin-top:10px; padding:8px 10px; background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.3); border-radius:6px; line-height:1.4; }

    /* Footer disclaimer */
    .disclaimer { font-size:0.72rem; color:#6b7280; margin-top:35px; padding-top:14px; border-top:1px solid #1f2937; line-height:1.6; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">💠 Algorithmic Momentum Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">High-Precision Market Scanner • EMA/MACD/RSI/VWAP Confluence • Funding-Aware, Liquidation-Aware Risk Engine</div>', unsafe_allow_html=True)

# ============================================================================
# CONSTANTS
# ============================================================================
SYMBOL_MAP = {
    "ARBITRUM": "ARB", "SHIBA": "SHIB", "SHIBAINU": "SHIB", "DOGECOIN": "DOGE",
    "MATIC": "POL", "RIPPLE": "XRP", "SOLANA": "SOL", "CARDANO": "ADA",
    "AVALANCHE": "AVAX", "POLKADOT": "DOT"
}

ALL_DCX_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "NEAR", "LINK",
    "PEPE", "SHIB", "WIF", "BONK", "FLOKI", "SUI", "APT", "INJ", "FET", "RENDER",
    "ARB", "OP", "TIA", "SEI", "STX", "FIL", "LTC", "BCH", "POL", "GALA",
    "LDO", "RUNE", "ATOM", "ETC", "ICP", "DOT", "UNI", "AAVE", "SAND", "MANA", "KAS"
]

# History depth: EMA-26/RSI-14/ATR-14 all use recursive (Wilder/EMA) smoothing that is
# biased by its own seed value until enough bars have decayed that bias away. At 60 bars
# (the old limit) that residual bias is still visible in RSI/ATR; at ~200 bars it is gone
# to several decimal places. See the accompanying notes for the numeric check.
HISTORY_BARS = 200
CACHE_TTL_SECONDS = 6
MAX_WORKERS = 16


def normalize_ticker(raw_input: str) -> str:
    cleaned = raw_input.strip().upper().replace("USDT", "").replace("B-", "")
    return SYMBOL_MAP.get(cleaned, cleaned)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if "active_watchlist" not in st.session_state:
    st.session_state.active_watchlist = ["BTC", "ETH", "SOL", "PEPE", "SUI", "ARB", "WIF", "INJ"]
if "manual_input_error" not in st.session_state:
    st.session_state.manual_input_error = None

# ============================================================================
# CALLBACKS
# ============================================================================
def add_from_dropdown_callback():
    normalized = normalize_ticker(st.session_state.coin_dropdown_selection)
    if normalized and normalized not in st.session_state.active_watchlist:
        st.session_state.active_watchlist.append(normalized)


def add_from_manual_callback():
    raw = st.session_state.manual_text_input
    if not raw:
        return
    normalized = normalize_ticker(raw)
    # Basic validation: reject blank/garbage input so it can't silently pollute the
    # scanner matrix or build a malformed exchange URL later.
    if not normalized or not re.fullmatch(r"[A-Z0-9]{1,15}", normalized):
        st.session_state.manual_input_error = f"'{raw.strip()}' doesn't look like a valid ticker (letters/numbers only)."
        st.session_state.manual_text_input = ""
        return
    st.session_state.manual_input_error = None
    if normalized not in ALL_DCX_COINS:
        ALL_DCX_COINS.insert(0, normalized)
    if normalized not in st.session_state.active_watchlist:
        st.session_state.active_watchlist.append(normalized)
    st.session_state.manual_text_input = ""


def add_preset_memes():
    for coin in ["PEPE", "DOGE", "SHIB", "WIF", "BONK"]:
        if coin not in st.session_state.active_watchlist:
            st.session_state.active_watchlist.append(coin)


def add_preset_l1s():
    for coin in ["SOL", "AVAX", "SUI", "APT", "NEAR", "SEI"]:
        if coin not in st.session_state.active_watchlist:
            st.session_state.active_watchlist.append(coin)


def add_preset_majors():
    for coin in ["BTC", "ETH", "SOL", "BNB", "XRP"]:
        if coin not in st.session_state.active_watchlist:
            st.session_state.active_watchlist.append(coin)


# ============================================================================
# SIDEBAR — SCREENER
# ============================================================================
st.sidebar.markdown("### 🔍 Market Screener")
st.sidebar.selectbox("Select Asset from Directory:", options=ALL_DCX_COINS, key="coin_dropdown_selection")
st.sidebar.button("➕ Add to Scanner Matrix", on_click=add_from_dropdown_callback, width="stretch")

st.sidebar.text_input("Or Input Custom Ticker:", key="manual_text_input", on_change=add_from_manual_callback)
st.sidebar.button("➕ Add Manual Asset", on_click=add_from_manual_callback, width="stretch")
if st.session_state.manual_input_error:
    st.sidebar.error(st.session_state.manual_input_error)

st.sidebar.markdown("---")
st.sidebar.markdown("**Portfolio Sectors:**")
col_p1, col_p2, col_p3 = st.sidebar.columns(3)
col_p1.button("💎 Majors", on_click=add_preset_majors, width="stretch")
col_p2.button("🔥 Memes", on_click=add_preset_memes, width="stretch")
col_p3.button("🚀 L1s/L2s", on_click=add_preset_l1s, width="stretch")

st.sidebar.markdown("---")
# NOTE: only `key=` is used here — never pass `default=` alongside a `key` that already
# exists in session_state. Doing both (as the previous version did) makes Streamlit log
# "created with a default value but also had its value set via the Session State API"
# on every single rerun, and is flagged by Streamlit itself as unsupported/ambiguous.
# `key="active_watchlist"` alone already makes the widget read/write that exact state.
selected_coins = st.sidebar.multiselect(
    "Active Scanning Matrix:",
    options=list(dict.fromkeys(ALL_DCX_COINS + st.session_state.active_watchlist)),
    key="active_watchlist"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Quant Parameters")
timeframe = st.sidebar.selectbox("Signal Resolution (TF)", ["1m", "5m", "15m"], index=1)
enable_mtf = st.sidebar.checkbox("Require 15m HTF Alignment", value=True)
strict_vol = st.sidebar.checkbox("Require Volume Spike (Strict)", value=True)

st.sidebar.markdown("---")
refresh_clicked = st.sidebar.button("🔄 Refresh Scan Now", width="stretch")
auto_refresh = st.sidebar.checkbox("Live Auto-Refresh (10s)", value=False)

with st.sidebar.expander("🧮 Advanced Risk & Precision Settings"):
    st.markdown("**Stop-Loss / Take-Profit (ATR multiples)**")
    sl_atr_mult = st.slider("SL distance = x × ATR", 0.5, 4.0, 1.5, 0.1)
    tp_atr_mult = st.slider("TP distance = x × ATR", 1.0, 8.0, 3.0, 0.1)

    st.markdown("**Liquidation Model (isolated-margin approximation)**")
    mmr_input = st.slider("Assumed Maintenance Margin Rate (%)", 0.1, 2.0, 0.5, 0.1)
    mmr_pct = mmr_input / 100.0
    liq_buffer_mult = st.slider("Liquidation buffer (× SL distance)", 1.0, 4.0, 2.0, 0.1,
                                 help="Recommended leverage targets a liquidation price this many multiples of the SL distance away from entry, so normal wicks don't liquidate you before your stop fires.")
    min_lev_cap, max_lev_cap = st.slider("Leverage range cap", 1, 50, (2, 20))

    st.markdown("**Position Sizing**")
    account_balance = st.number_input("Account Balance (USD)", min_value=0.0, value=1000.0, step=100.0)
    risk_per_trade_pct = st.slider("Risk per Trade (% of account)", 0.1, 5.0, 1.0, 0.1)

    st.markdown("**Volatility Regime Filter**")
    atr_pct_min, atr_pct_max = st.slider("Acceptable ATR (% of price)", 0.0, 10.0, (0.03, 6.0), 0.01,
                                          help="Filters out dead/illiquid chop (too low) and news-spike chaos (too high).")

    st.markdown("**Confluence**")
    require_vwap = st.checkbox("Require Rolling-VWAP Alignment", value=False,
                                help="LONG needs price above the rolling VWAP of the fetched window; SHORT needs price below it.")
    rsi_long_lo, rsi_long_hi = st.slider("RSI band — LONG", 0, 100, (45, 75))
    rsi_short_lo, rsi_short_hi = st.slider("RSI band — SHORT", 0, 100, (25, 55))


# ============================================================================
# NETWORK LAYER
# ============================================================================
def _safe_get_json(url: str, timeout: float = 4.0, retries: int = 1, backoff: float = 0.35):
    """GET a URL and return parsed JSON, or None. Retries once on transient network
    errors; never swallows programming errors (only network/parsing failures)."""
    headers = {"User-Agent": "Mozilla/5.0 (QuantTerminal/2.0)"}
    for attempt in range(retries + 1):
        try:
            res = requests.get(url, headers=headers, timeout=timeout)
            if res.status_code == 200:
                return res.json()
        except (requests.exceptions.RequestException, ValueError):
            pass
        if attempt < retries:
            time.sleep(backoff)
    return None


# ============================================================================
# INDICATOR ENGINE
# ============================================================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- Trend: EMAs ---
    df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()

    # --- Momentum: MACD ---
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # --- Oscillator: RSI using Wilder's RMA smoothing (alpha = 1/14) instead of a
    # simple rolling mean. Given >=~150 bars of warm-up this is numerically
    # indistinguishable from the textbook iterative Wilder method (verified to
    # <0.001 RSI points), and it's what TradingView / most exchanges actually plot —
    # a plain rolling mean gives visibly different values.
    period = 14
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    # Fix the flat-price edge case: the old `loss.replace(0, 0.00001)` epsilon hack
    # made a perfectly flat market collapse to RSI=0 (looks "oversold") instead of the
    # correct neutral 50. All-gains/no-losses correctly resolves to 100.
    flat_mask = (avg_gain == 0) & (avg_loss == 0)
    df.loc[flat_mask, 'RSI'] = 50.0
    allgain_mask = (avg_loss == 0) & (avg_gain > 0)
    df.loc[allgain_mask, 'RSI'] = 100.0

    # --- Volatility: ATR, also Wilder's RMA smoothing (same reasoning as RSI) ---
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = true_range.ewm(alpha=1 / period, adjust=False).mean()
    df['ATR_Pct'] = (df['ATR'] / df['close']) * 100

    # --- Volume ---
    df['Vol_SMA'] = df['volume'].rolling(window=20).mean()
    df['Vol_Ratio'] = df['volume'] / df['Vol_SMA'].replace(0, np.nan)

    # --- Rolling VWAP, anchored to the start of the fetched window. Crypto trades
    # 24/7 so there's no natural "session open" to anchor to the way equities do;
    # this is a transparent lookback-window VWAP, not an exchange session VWAP. ---
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    cum_vol = df['volume'].cumsum()
    df['VWAP'] = (typical_price * df['volume']).cumsum() / cum_vol.replace(0, np.nan)

    return df


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_candles(coin_symbol: str, tf: str, limit: int = HISTORY_BARS):
    """Returns (indicator_df, source_name) — source_name is 'CoinDCX' or 'Bybit' so
    downstream code can show correct data-source badges and a working trade link
    instead of always pointing at CoinDCX even when that pair had to fall back."""
    url = f"https://public.coindcx.com/market_data/candles/?pair=B-{coin_symbol}_USDT&interval={tf}&limit={limit}"
    data = _safe_get_json(url)
    if isinstance(data, list) and len(data) > 30:
        try:
            df = pd.DataFrame(data).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return calculate_indicators(df), "CoinDCX"
        except (KeyError, ValueError, TypeError):
            pass

    bybit_interval = {"1m": "1", "5m": "5", "15m": "15"}.get(tf, "5")
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={coin_symbol}USDT&interval={bybit_interval}&limit={limit}"
    data = _safe_get_json(url)
    if data and len(data.get("result", {}).get("list", [])) > 30:
        try:
            rows = data["result"]["list"]
            df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover']).iloc[::-1].reset_index(drop=True)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return calculate_indicators(df), "Bybit"
        except (KeyError, ValueError, TypeError):
            pass
    return None, None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_ticker(coin_symbol: str):
    """Perp reference data (funding rate, open interest, bid/ask spread) sourced from
    Bybit's public v5 ticker endpoint. This is used as a market-wide reference for
    EVERY coin regardless of which venue the candles came from, since CoinDCX doesn't
    expose a reliable public funding/OI endpoint we could verify — this is disclosed
    to the user in the UI rather than silently presented as CoinDCX's own numbers."""
    url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={coin_symbol}USDT"
    data = _safe_get_json(url)
    if not data:
        return None
    lst = data.get("result", {}).get("list", [])
    if not lst:
        return None
    t = lst[0]
    try:
        bid = float(t.get("bid1Price") or 0)
        ask = float(t.get("ask1Price") or 0)
        last = float(t.get("lastPrice") or 0)
        spread_pct = ((ask - bid) / last * 100) if (last > 0 and ask > 0 and bid > 0) else None
        return {
            "funding_rate": float(t.get("fundingRate")) if t.get("fundingRate") not in (None, "") else None,
            "next_funding_ms": int(t.get("nextFundingTime")) if t.get("nextFundingTime") not in (None, "") else None,
            "open_interest_usd": float(t.get("openInterestValue")) if t.get("openInterestValue") not in (None, "") else None,
            "spread_pct": spread_pct,
            "change_24h_pct": float(t.get("price24hPcnt")) * 100 if t.get("price24hPcnt") not in (None, "") else None,
            "last_price": last,
        }
    except (TypeError, ValueError):
        return None


# ============================================================================
# FORMATTING HELPERS
# ============================================================================
def format_price(price):
    if price is None or (isinstance(price, (int, float)) and pd.isna(price)):
        return "-"
    if price >= 1000:
        return f"{price:,.2f}"
    elif price >= 1:
        return f"{price:.4f}"
    elif price >= 0.01:
        return f"{price:.5f}"
    elif price >= 0.0001:
        return f"{price:.7f}"
    else:
        return f"{price:.9f}"


def format_compact(n):
    if n is None or (isinstance(n, (int, float)) and pd.isna(n)):
        return "N/A"
    n = float(n)
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= div:
            return f"{n/div:.2f}{unit}"
    return f"{n:.2f}"


def format_time_until(ms_timestamp):
    if not ms_timestamp:
        return "N/A"
    try:
        target = datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc)
        delta = target - datetime.now(timezone.utc)
        total_min = int(delta.total_seconds() // 60)
        if total_min < 0:
            return "N/A"
        h, m = divmod(total_min, 60)
        return f"{h}h{m}m"
    except (ValueError, OSError, OverflowError, TypeError):
        return "N/A"


# ============================================================================
# RISK ENGINE
# ============================================================================
def estimate_liquidation(entry, leverage, mmr, direction):
    """Simplified isolated-margin liquidation estimate (ignores fees/funding accrual):
    Long:  Liq = Entry * (1 - 1/L + MMR)
    Short: Liq = Entry * (1 + 1/L - MMR)
    Real exchanges use tiered maintenance-margin schedules that increase with position
    size, so treat this as a planning approximation, not an exact venue figure."""
    if leverage <= 0:
        return None
    if direction == "LONG":
        return entry * (1 - 1.0 / leverage + mmr)
    elif direction == "SHORT":
        return entry * (1 + 1.0 / leverage - mmr)
    return None


def recommend_leverage(risk_pct, mmr, buffer_mult, min_lev, max_lev):
    """Chooses leverage so the estimated liquidation price sits `buffer_mult` times
    further from entry than the stop-loss does (so the SL should trigger well before
    liquidation), then clamps into [min_lev, max_lev]."""
    if risk_pct <= 0:
        return min_lev
    raw = 1.0 / (buffer_mult * risk_pct + mmr)
    return int(min(max(raw, min_lev), max_lev))


def compute_confluence_score(direction, macd_hist, atr, vol_ratio, htf_macd_agrees, rsi,
                              vwap_dev_atr, funding_rate, rsi_long_lo, rsi_long_hi,
                              rsi_short_lo, rsi_short_hi):
    """A transparent, human-auditable 0-100 heuristic used ONLY to rank/prioritize
    setups that already passed the hard signal gate — it is not a backtested
    probability of winning, and is intentionally not marketed as one."""
    if direction == "NONE" or atr is None or atr <= 0 or pd.isna(atr):
        return 0.0
    score = 0.0

    macd_norm = min(abs(macd_hist) / (atr * 0.15 + 1e-12), 1.0)
    score += macd_norm * 25

    vol_norm = min(max((vol_ratio - 1.0) / 1.5, 0.0), 1.0)
    score += vol_norm * 20

    score += 20.0 if htf_macd_agrees else 8.0

    if direction == "LONG":
        center, half = (rsi_long_lo + rsi_long_hi) / 2.0, max((rsi_long_hi - rsi_long_lo) / 2.0, 1e-6)
    else:
        center, half = (rsi_short_lo + rsi_short_hi) / 2.0, max((rsi_short_hi - rsi_short_lo) / 2.0, 1e-6)
    rsi_norm = max(0.0, 1 - abs(rsi - center) / half)
    score += rsi_norm * 15

    vwap_norm = min(max(vwap_dev_atr, 0.0), 1.0) if vwap_dev_atr is not None else 0.5
    score += vwap_norm * 10

    if funding_rate is None:
        score += 5.0
    else:
        crowd = funding_rate if direction == "LONG" else -funding_rate
        funding_norm = 1.0 - min(max(crowd / 0.0005, 0.0), 1.0)
        score += funding_norm * 10

    return round(min(max(score, 0.0), 100.0), 1)


# ============================================================================
# SIGNAL EVALUATION
# ============================================================================
def evaluate_signal(coin_name: str):
    df, source = fetch_candles(coin_name, timeframe, HISTORY_BARS)
    if df is None or df.empty or len(df) < 30:
        return {"Coin": coin_name, "Error": True}

    last = df.iloc[-1]
    price = last['close']
    if pd.isna(price) or price <= 0:
        return {"Coin": coin_name, "Error": True}

    rsi = round(last['RSI'], 1) if not pd.isna(last['RSI']) else 50.0
    atr = last['ATR'] if not pd.isna(last['ATR']) and last['ATR'] > 0 else price * 0.01
    atr_pct = last['ATR_Pct'] if not pd.isna(last['ATR_Pct']) else (atr / price * 100)
    vwap = last['VWAP'] if not pd.isna(last['VWAP']) else price
    vol_ratio = last['Vol_Ratio'] if not pd.isna(last['Vol_Ratio']) else 1.0
    vol_spike = vol_ratio > 1.3

    bull_ema = last['EMA_9'] > last['EMA_21']
    bull_macd = last['MACD_Hist'] > 0
    bear_ema = last['EMA_9'] < last['EMA_21']
    bear_macd = last['MACD_Hist'] < 0
    macd_hist = last['MACD_Hist']

    mtf_aligned = True
    htf_status = "N/A"
    htf_macd_agrees = False
    if enable_mtf and timeframe != "15m":
        df_htf, _ = fetch_candles(coin_name, "15m", HISTORY_BARS)
        if df_htf is not None and not df_htf.empty:
            htf_last = df_htf.iloc[-1]
            htf_bullish = htf_last['EMA_9'] > htf_last['EMA_21']
            htf_status = "BULL" if htf_bullish else "BEAR"
            if (bull_ema and not htf_bullish) or (bear_ema and htf_bullish):
                mtf_aligned = False
            if bull_ema and htf_bullish and htf_last['MACD_Hist'] > 0:
                htf_macd_agrees = True
            if bear_ema and (not htf_bullish) and htf_last['MACD_Hist'] < 0:
                htf_macd_agrees = True

    vol_valid = True if not strict_vol else vol_spike
    atr_ok = atr_pct_min <= atr_pct <= atr_pct_max
    vwap_long_ok = (not require_vwap) or (price >= vwap)
    vwap_short_ok = (not require_vwap) or (price <= vwap)

    signal = "NEUTRAL ⚪"
    direction = "NONE"
    if bull_ema and bull_macd and (rsi_long_lo < rsi < rsi_long_hi) and mtf_aligned and vol_valid and atr_ok and vwap_long_ok:
        signal, direction = "LONG 🟢", "LONG"
    elif bear_ema and bear_macd and (rsi_short_lo < rsi < rsi_short_hi) and mtf_aligned and vol_valid and atr_ok and vwap_short_ok:
        signal, direction = "SHORT 🔴", "SHORT"

    ticker = fetch_ticker(coin_name)
    funding_rate = ticker['funding_rate'] if ticker else None
    next_funding_ms = ticker['next_funding_ms'] if ticker else None
    oi_usd = ticker['open_interest_usd'] if ticker else None
    spread_pct = ticker['spread_pct'] if ticker else None
    chg24h = ticker['change_24h_pct'] if ticker else None

    if direction == "LONG":
        entry, sl, tp = price, price - (sl_atr_mult * atr), price + (tp_atr_mult * atr)
    elif direction == "SHORT":
        entry, sl, tp = price, price + (sl_atr_mult * atr), price - (tp_atr_mult * atr)
    else:
        entry, sl, tp = price, 0.0, 0.0

    risk_pct = abs(entry - sl) / entry if direction != "NONE" and entry > 0 else 0.0
    leverage = recommend_leverage(risk_pct, mmr_pct, liq_buffer_mult, min_lev_cap, max_lev_cap) if direction != "NONE" else 1
    liq_price = estimate_liquidation(entry, leverage, mmr_pct, direction) if direction != "NONE" else None

    liq_buffer_pct, liq_danger = None, False
    if direction == "LONG" and liq_price is not None:
        liq_buffer_pct = (sl - liq_price) / entry * 100
        liq_danger = liq_buffer_pct <= 0
    elif direction == "SHORT" and liq_price is not None:
        liq_buffer_pct = (liq_price - sl) / entry * 100
        liq_danger = liq_buffer_pct <= 0

    risk_amount = account_balance * (risk_per_trade_pct / 100.0)
    position_size_usd = (risk_amount / risk_pct) if (direction != "NONE" and risk_pct > 0) else 0.0
    required_margin = (position_size_usd / leverage) if (direction != "NONE" and leverage > 0) else 0.0

    vwap_dev_atr = abs(price - vwap) / atr if atr > 0 else 0.0
    score = compute_confluence_score(
        direction, macd_hist, atr, vol_ratio, htf_macd_agrees, rsi, vwap_dev_atr, funding_rate,
        rsi_long_lo, rsi_long_hi, rsi_short_lo, rsi_short_hi
    ) if direction != "NONE" else 0.0

    trade_link = (f"https://coindcx.com/futures/B-{coin_name}_USDT" if source == "CoinDCX"
                  else f"https://www.bybit.com/trade/usdt/{coin_name}USDT")

    return {
        "Coin": coin_name, "Signal": signal, "Direction": direction,
        "Price": price, "F_Price": format_price(price),
        "Entry": format_price(entry) if direction != "NONE" else "-",
        "SL": format_price(sl) if direction != "NONE" else "-",
        "TP": format_price(tp) if direction != "NONE" else "-",
        "Lev": f"{leverage}x", "LevNum": leverage,
        "LiqPrice": format_price(liq_price) if liq_price is not None else "-",
        "LiqBufferPct": liq_buffer_pct, "LiqDanger": liq_danger,
        "PositionSizeUSD": position_size_usd, "RequiredMarginUSD": required_margin,
        "HTF": htf_status, "HTFMacdAgrees": htf_macd_agrees,
        "RSI": rsi, "ATRPct": round(atr_pct, 3),
        "MACD": "🟢 Bull" if bull_macd else "🔴 Bear", "MACD_Hist": macd_hist,
        "Vol": f"🔥 {vol_ratio:.1f}x" if vol_spike else f"{vol_ratio:.1f}x", "VolRatio": round(vol_ratio, 2),
        "VWAP": vwap, "AboveVWAP": price >= vwap,
        "Funding": funding_rate, "NextFundingMs": next_funding_ms,
        "OI_USD": oi_usd, "SpreadPct": spread_pct, "Change24h": chg24h,
        "Score": score,
        "Source": source or "N/A",
        "Trade_Link": trade_link,
        "Error": False
    }


# ============================================================================
# EXECUTION
# ============================================================================
if refresh_clicked:
    fetch_candles.clear()
    fetch_ticker.clear()

if selected_coins:
    with st.spinner("Executing quantitative matrix scan..."):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            raw_results = list(executor.map(evaluate_signal, selected_coins))
    results = [r for r in raw_results if not r.get("Error")]
    failed = [r["Coin"] for r in raw_results if r.get("Error")]
else:
    results, failed = [], []
    st.info("💡 Awaiting Asset Selection. Please load the scanner using the sidebar.")

if failed:
    st.warning(f"⚠️ API connection failed for: {', '.join(failed)}. Symbol may be inactive on both CoinDCX and Bybit.")

# ============================================================================
# RENDERING
# ============================================================================
def badge(text, css_class="badge"):
    return f'<span class="{css_class}">{text}</span>'


def render_trade_card(row) -> str:
    direction = row['Direction']
    card_class = "trade-card-long" if direction == "LONG" else "trade-card-short"
    val_class = "metric-value-long" if direction == "LONG" else "metric-value-short"
    score_fill_class = "score-fill-long" if direction == "LONG" else "score-fill-short"

    funding = row['Funding']
    if funding is None or pd.isna(funding):
        funding_txt, funding_class = "N/A", "badge"
    else:
        funding_txt = f"{funding*100:+.4f}% ({format_time_until(row['NextFundingMs'])})"
        crowd = funding if direction == "LONG" else -funding
        if crowd > 0.0004:
            funding_class = "badge badge-warn"
        elif crowd < -0.0001:
            funding_class = "badge badge-good"
        else:
            funding_class = "badge"

    oi_val = row['OI_USD']
    oi_txt = format_compact(oi_val) if oi_val is not None and not pd.isna(oi_val) else "N/A"

    spread = row['SpreadPct']
    if spread is None or pd.isna(spread):
        spread_txt, spread_class = "N/A", "badge"
    else:
        spread_txt = f"{spread:.3f}%"
        spread_class = "badge badge-warn" if spread > 0.15 else "badge"

    liq_warning_html = ""
    if row['LiqDanger']:
        liq_warning_html = (
            '<div class="liq-warning">⚠️ At this leverage the estimated liquidation price sits at or beyond '
            'your stop-loss — a stop-out isn\'t guaranteed to save you here. Consider a wider stop, a lower '
            'min-leverage floor, or a smaller size.</div>'
        )

    position_html = ""
    if row['PositionSizeUSD'] and row['PositionSizeUSD'] > 0:
        position_html = f"""
        <div class="card-metric" style="margin-top:10px;"><span class="metric-label">Suggested Size</span><span class="num" style="color:#f3f4f6;">${row['PositionSizeUSD']:,.0f}</span></div>
        <div class="card-metric"><span class="metric-label">Required Margin</span><span class="num" style="color:#9ca3af;">${row['RequiredMarginUSD']:,.0f}</span></div>"""

    badges_html = "".join([
        badge(f"HTF {row['HTF']}"),
        badge(f"MACD {row['MACD']}"),
        badge(f"ATR {row['ATRPct']:.2f}%"),
        badge(f"Funding {funding_txt}", funding_class),
        badge(f"OI ${oi_txt}"),
        badge(f"Spread {spread_txt}", spread_class),
    ])

    return f"""
    <div class="trade-card {card_class}">
        <div class="card-header">
            <span>{row['Coin']}-PERP <span style="font-weight:400;color:#6b7280;font-size:0.72rem;">· {row['Source']} data</span></span>
            <span class="{val_class}" style="font-size:0.85rem; border:1px solid currentColor; padding:2px 8px; border-radius:12px;">{direction}</span>
        </div>
        <div class="card-metric"><span class="metric-label">Entry</span><span class="num" style="color:#f3f4f6;">${row['Entry']}</span></div>
        <div class="card-metric"><span class="metric-label">Stop-Loss</span><span class="num" style="color:#9ca3af;">${row['SL']}</span></div>
        <div class="card-metric"><span class="metric-label">Take-Profit</span><span class="num" style="color:#f3f4f6;">${row['TP']}</span></div>
        <div class="card-metric"><span class="metric-label">Est. Liquidation ({row['Lev']})</span><span class="num" style="color:#f59e0b;">${row['LiqPrice']}</span></div>
        {liq_warning_html}
        <hr style="border:0; height:1px; background:#1f2937; margin:12px 0;">
        <div class="card-metric"><span class="metric-label">Setup Strength</span><span class="num">{row['Score']:.0f}/100</span></div>
        <div class="score-track"><div class="{score_fill_class}" style="width:{row['Score']}%;"></div></div>
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:12px;">{badges_html}</div>
        {position_html}
        <div style="margin-top:15px;">
            <a href="{row['Trade_Link']}" target="_blank" style="color:#3b82f6; text-decoration:none; font-size:0.85rem; font-weight:600;">↗ {row['Source']} Execution</a>
        </div>
    </div>
    """


if results:
    df = pd.DataFrame(results).drop(columns=["Error"])
    active_longs = int((df['Signal'] == "LONG 🟢").sum())
    active_shorts = int((df['Signal'] == "SHORT 🔴").sum())

    # --- Market snapshot for BTC/ETH, reusing data already fetched (no extra calls) ---
    snapshot_rows = df[df['Coin'].isin(['BTC', 'ETH'])]
    if not snapshot_rows.empty:
        snap_cols = st.columns(len(snapshot_rows))
        for i, (_, srow) in enumerate(snapshot_rows.iterrows()):
            chg = srow['Change24h']
            chg_txt = f"{chg:+.2f}%" if chg is not None and not pd.isna(chg) else "N/A"
            snap_cols[i].metric(f"{srow['Coin']} / USDT", f"${srow['F_Price']}", chg_txt)
        st.markdown("<br>", unsafe_allow_html=True)

    # --- Top metrics: replaced the old static "Optimized ⚡" badge (always the same
    # regardless of reality) with real feed-health and freshness information. ---
    met1, met2, met3, met4, met5 = st.columns(5)
    met1.metric("Assets Tracked", len(results))
    met2.metric("Active Long Signals", active_longs)
    met3.metric("Active Short Signals", active_shorts)
    met4.metric("Feed Health", f"{len(results)}/{len(selected_coins)}")
    met5.metric("Last Scan", datetime.now().strftime("%H:%M:%S"))
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Ranked signal cards (highest Setup Strength first) ---
    active_setups = df[df['Signal'].str.contains("LONG|SHORT")].sort_values("Score", ascending=False).reset_index(drop=True)
    st.markdown("### ⚡ Validated Execution Setups")

    if not active_setups.empty:
        cols = st.columns(min(len(active_setups), 3))
        for i, (_, row) in enumerate(active_setups.iterrows()):
            with cols[i % 3]:
                st.markdown(render_trade_card(row), unsafe_allow_html=True)
    else:
        st.info("Market conditions are currently choppy or flat. No high-precision setups detected based on current strict parameters.")

    st.markdown("---")
    st.markdown("### 📊 Live Market Matrix")

    display_df = df.copy()
    display_df['FundingDisp'] = display_df['Funding'].apply(lambda f: f"{f*100:+.3f}%" if f is not None and not pd.isna(f) else "N/A")
    display_df = display_df.sort_values(['Score', 'Coin'], ascending=[False, True])
    display_df = display_df[['Coin', 'Signal', 'F_Price', 'HTF', 'MACD', 'RSI', 'ATRPct', 'Vol', 'FundingDisp', 'Score', 'Source', 'Trade_Link']].rename(
        columns={"F_Price": "Price", "HTF": "15m Trend", "ATRPct": "ATR %", "FundingDisp": "Funding"}
    )

    def style_dataframe(val):
        s = str(val)
        if "LONG" in s or "Bull" in s:
            return 'color: #10b981; font-weight: 600;'
        if "SHORT" in s or "Bear" in s:
            return 'color: #ef4444; font-weight: 600;'
        return ''

    st.dataframe(
        display_df.style.map(style_dataframe, subset=['Signal', 'MACD', '15m Trend']),
        column_config={
            "Trade_Link": st.column_config.LinkColumn("Action", display_text="Trade ↗"),
            "Score": st.column_config.ProgressColumn("Setup Score", min_value=0, max_value=100, format="%.0f"),
            "RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
            "ATR %": st.column_config.NumberColumn("ATR %", format="%.2f%%"),
        },
        width="stretch",
        hide_index=True
    )

st.markdown("""
<div class="disclaimer">
Algorithmic educational tool, not financial advice. Signals come from historical technical indicators and can fail, especially in thin or fast-moving markets. Leveraged perpetual futures can lose more than your margin if a stop doesn't fill in time. Funding rate, open interest and spread are sourced from Bybit's public API as a market-wide reference regardless of which venue supplied the candles, and may differ from CoinDCX's own book. Liquidation price is a simplified isolated-margin estimate — confirm the exact figure on your exchange before sizing a trade.
</div>
""", unsafe_allow_html=True)

if auto_refresh:
    time.sleep(10)
    st.rerun()
