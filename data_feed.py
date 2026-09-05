from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests


# ============================================================
# Configuration
# ============================================================

DEFAULT_SYMBOL = "DASHUSDT"
DEFAULT_TIMEFRAME = "1D"

TRADINGVIEW_EXCHANGE = os.getenv("TRADINGVIEW_EXCHANGE", "BINGX")


# ============================================================
# TradingView (منبع اصلی)
# ============================================================

def load_from_tradingview(
    symbol: str,
    n_bars: int = 5000,
) -> pd.DataFrame:

    from tvDatafeed import TvDatafeed, Interval

    username = os.getenv("TV_USERNAME")
    password = os.getenv("TV_PASSWORD")

    if username and password:
        tv = TvDatafeed(username, password)
    else:
        tv = TvDatafeed()

    df = tv.get_hist(
        symbol=symbol,
        exchange=TRADINGVIEW_EXCHANGE,
        interval=Interval.in_daily,
        n_bars=n_bars,
        extended_session=False,
    )

    if df is None or df.empty:
        raise RuntimeError("TradingView returned no data.")

    df = df.copy()

    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()

    if "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    elif "time" in df.columns:
        df = df.rename(columns={"time": "timestamp"})

    required = ["timestamp", "open", "high", "low", "close", "volume"]

    for col in required:
        if col not in df.columns:
            if col == "volume":
                df["volume"] = 0.0
            else:
                raise RuntimeError(f"TradingView missing column: {col}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = (
        df[required]
        .dropna(subset=["open", "high", "low", "close"])
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# BingX Spot API (دقیقاً مطابق TradingView)
# ============================================================

def load_from_bingx(
    symbol: str,
    n_bars: int = 5000,
) -> pd.DataFrame:
    """
    BingX Spot API - منبع داده‌ای که TradingView برای BINGX:DASHUSDT استفاده می‌کند.
    ساختار داده دقیقاً مطابق اسپات BingX است.
    """
    url = "https://open-api.bingx.com/openApi/spot/v1/klines"
    
    interval = "1d"
    limit = 1000
    all_rows = []
    end_ms: Optional[int] = None
    
    # در اسپات BingX، نماد بدون خط تیره است: DASHUSDT
    clean_symbol = symbol.upper().replace("-", "")
    
    while len(all_rows) < n_bars:
        params = {
            "symbol": clean_symbol,
            "interval": interval,
            "limit": limit,
        }
        
        if end_ms is not None:
            params["endTime"] = end_ms
        
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        
        if payload.get("code") != 0:
            raise RuntimeError(payload.get("msg", "BingX Spot API error"))
        
        rows = payload.get("data", [])
        
        if not rows:
            break
        
        all_rows.extend(rows)
        
        # در اسپات، هر row یک آرایه است: [timestamp, open, high, low, close, volume, ...]
        # row[0] = timestamp (میلی‌ثانیه)
        oldest = int(rows[0][0])
        new_end = oldest - 1
        
        if end_ms is not None and new_end >= end_ms:
            break
        
        end_ms = new_end
        
        if len(rows) < limit:
            break
    
    if not all_rows:
        raise RuntimeError("BingX returned no data.")
    
    # مرتب‌سازی از قدیمی به جدید
    all_rows = sorted(all_rows, key=lambda x: int(x[0]))
    all_rows = all_rows[-n_bars:]
    
    # ساخت DataFrame از آرایه‌ها
    df = pd.DataFrame(
        all_rows,
        columns=[
            "timestamp",      # [0]
            "open",           # [1]
            "high",           # [2]
            "low",            # [3]
            "close",          # [4]
            "volume",         # [5]
            "close_time",     # [6]
            "quote_volume",   # [7]
            "trades",         # [8]
            "taker_buy_base", # [9]
            "taker_buy_quote",# [10]
            "ignore"          # [11]
        ],
    )
    
    # تبدیل timestamp از میلی‌ثانیه به datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True)
    
    # تبدیل ستون‌های عددی
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # انتخاب و تمیزکاری نهایی ستون‌ها
    df = (
        df[["timestamp", "open", "high", "low", "close", "volume"]]
        .dropna()
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    
    return df


# ============================================================
# Automatic failover
# ============================================================

def load_market_data(
    symbol: str = DEFAULT_SYMBOL,
    n_bars: int = 5000,
):
    errors = []
    
    # اولویت ۱: TradingView
    try:
        df = load_from_tradingview(symbol=symbol, n_bars=n_bars)
        return df, "TradingView"
    except Exception as exc:
        errors.append(f"TradingView: {type(exc).__name__}: {exc}")
    
    # اولویت ۲: BingX Spot API (دقیقاً همان داده‌های TradingView)
    try:
        df = load_from_bingx(symbol=symbol, n_bars=n_bars)
        return df, "BingX"
    except Exception as exc:
        errors.append(f"BingX: {type(exc).__name__}: {exc}")
    
    raise RuntimeError(
        "All permitted data sources failed:\n\n" + "\n".join(errors)
    )