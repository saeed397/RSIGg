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
# BingX Market API (ضدگلوله و دقیقاً مطابق TradingView)
# ============================================================

def load_from_bingx(
    symbol: str,
    n_bars: int = 5000,
) -> pd.DataFrame:
    """
    BingX Historical K-line API.
    این نسخه به گونه‌ای نوشته شده که بدون توجه به تعداد ستون‌های اضافی
    بازگشتی توسط API، فقط ۶ ستون اصلی OHLCV را استخراج می‌کند.
    """
    url = "https://open-api.bingx.com/openApi/market/his/v1/kline"
    
    interval = "1d"
    limit = 500  # حداکثر مقدار مجاز در این اندپوینت
    all_rows = []
    end_ms: Optional[int] = None
    
    clean_symbol = symbol.upper()
    if "USDT" in clean_symbol and "-" not in clean_symbol:
        clean_symbol = clean_symbol.replace("USDT", "-USDT")
    
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
            raise RuntimeError(payload.get("msg", "BingX API error"))
        
        rows = payload.get("data", [])
        
        if not rows:
            break
        
        all_rows.extend(rows)
        
        # row[0] همیشه timestamp است
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
    
    # ============================================================
    # تغییر حیاتی برای رفع خطای ValueError:
    # ساخت DataFrame بدون تعیین سخت‌گیرانه نام ستون‌ها
    # ============================================================
    df = pd.DataFrame(all_rows)
    
    # فقط ۶ ستون اول را نگه می‌داریم (این ترتیب در تمام APIهای استاندارد کریپتو ثابت است)
    # 0: timestamp, 1: open, 2: high, 3: low, 4: close, 5: volume
    df = df.iloc[:, :6]
    
    # نام‌گذاری ستون‌های استخراج‌شده
    df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
    
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True)
    
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
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
    
    try:
        df = load_from_tradingview(symbol=symbol, n_bars=n_bars)
        return df, "TradingView"
    except Exception as exc:
        errors.append(f"TradingView: {type(exc).__name__}: {exc}")
    
    try:
        df = load_from_bingx(symbol=symbol, n_bars=n_bars)
        return df, "BingX"
    except Exception as exc:
        errors.append(f"BingX: {type(exc).__name__}: {exc}")
    
    raise RuntimeError(
        "All permitted data sources failed:\n\n" + "\n".join(errors)
    )