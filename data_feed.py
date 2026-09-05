from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests


# ============================================================
# Configuration
# ============================================================

DEFAULT_SYMBOL = "DASH-USDT"
DEFAULT_TIMEFRAME = "1D"

TRADINGVIEW_EXCHANGE = os.getenv(
    "TRADINGVIEW_EXCHANGE",
    "BINGX"
)


# ============================================================
# TradingView
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
        interval=Interval.in_4_hour,
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
# BingX fallback
# ============================================================

def load_from_bingx(
    symbol: str,
    n_bars: int = 5000,
) -> pd.DataFrame:

    # 1. آدرس تمیز بدون پارامترهای چسبیده
    url = "https://open-api.bingx.com/openApi/swap/v3/quote/klines"

    interval = "240"
    limit = 1000
    all_rows = []
    end_ms: Optional[int] = None

    # اصلاح فرمت نماد برای اطمینان (تبدیل DASHUSDT به DASH-USDT)
    clean_symbol = symbol.upper()
    if "USDT" in clean_symbol and "-" not in clean_symbol:
        clean_symbol = clean_symbol.replace("USDT", "-USDT")

    while len(all_rows) < n_bars:
        # 2. حذف "category" چون مخصوص بای‌بیت است
        params = {
            "symbol": clean_symbol,
            "interval": interval,
            "limit": limit,
        }

        if end_ms is not None:
            params["endTime"] = end_ms

        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        response.raise_for_status()
        payload = response.json()

        # 3. بررسی کد پاسخ بینگ‌اکس (کد 0 یعنی موفقیت)
        if payload.get("code") != 0:
            raise RuntimeError(payload.get("msg", "BingX API error"))

        rows = payload.get("data", [])

        if not rows:
            break

        all_rows.extend(rows)

        oldest = min(int(row[0]) for row in rows)
        new_end = oldest - 1

        if end_ms is not None and new_end >= end_ms:
            break

        end_ms = new_end

        if len(rows) < limit:
            break

    if not all_rows:
        raise RuntimeError("BingX returned no data.")

    all_rows = sorted(all_rows, key=lambda x: int(x[0]))
    all_rows = all_rows[-n_bars:]

    df = pd.DataFrame(
        all_rows,
        columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],
    )

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
        # 4. اصلاح نام صرافی در پیام خطا
        errors.append(f"BingX: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        "All permitted data sources failed:\n\n" + "\n".join(errors)
    )