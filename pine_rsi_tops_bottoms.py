from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PineConfig:
    # Exactly from supplied Pine Script
    length: int = 14
    source: str = "close"
    ob: float = 70.0
    os: float = 30.0
    prd: int = 10
    mindis: int = 5
    maxdis: int = 100


def pine_rma(source: np.ndarray, length: int) -> np.ndarray:
    """
    TradingView/Pine RMA:
        alpha = 1 / length
        RMA = alpha * source + (1-alpha) * previous_RMA

    Initial value:
        SMA(source, length)

    This is intentionally implemented without pandas-ta.
    """

    n = len(source)
    out = np.full(n, np.nan, dtype=np.float64)

    if n == 0:
        return out

    alpha = 1.0 / float(length)

    # Pine's RMA starts after a complete SMA window.
    if n < length:
        return out

    first_window = source[:length]

    if np.isnan(first_window).any():
        return out

    out[length - 1] = np.mean(first_window)

    for i in range(length, n):
        x = source[i]

        if np.isnan(x):
            out[i] = np.nan
        else:
            out[i] = alpha * x + (1.0 - alpha) * out[i - 1]

    return out


def pine_rsi(close: np.ndarray, length: int = 14) -> np.ndarray:
    """
    Equivalent mathematical structure to:

        rsi(src, len)

    from the supplied Pine v4 script.
    """

    close = np.asarray(close, dtype=np.float64)

    n = len(close)

    change = np.full(n, np.nan, dtype=np.float64)

    if n > 1:
        change[1:] = close[1:] - close[:-1]

    # Pine:
    # u = max(x - x[1], 0)
    # d = max(x[1] - x, 0)

    up = np.where(
        np.isnan(change),
        np.nan,
        np.maximum(change, 0.0)
    )

    down = np.where(
        np.isnan(change),
        np.nan,
        np.maximum(-change, 0.0)
    )

    avg_up = pine_rma(up, length)
    avg_down = pine_rma(down, length)

    rsi = np.full(n, np.nan, dtype=np.float64)

    for i in range(n):
        u = avg_up[i]
        d = avg_down[i]

        if np.isnan(u) or np.isnan(d):
            continue

        if d == 0.0:
            rsi[i] = 100.0
        elif u == 0.0:
            rsi[i] = 0.0
        else:
            rs = u / d
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def _pine_bool(value) -> bool:
    """
    Pine bool series cannot actually be NA.
    Historical bool references that do not exist evaluate false.
    """
    return bool(value)


def calculate_indicator(
    df: pd.DataFrame,
    config: PineConfig = PineConfig(),
) -> pd.DataFrame:

    required = {"open", "high", "low", "close"}

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    data = df.copy().reset_index(drop=True)

    close = data["close"].astype(float).to_numpy()
    high = data["high"].astype(float).to_numpy()
    low = data["low"].astype(float).to_numpy()

    n = len(data)

    rsi = pine_rsi(close, config.length)

    data["rsi"] = rsi

    # ------------------------------------------------------------------
    # Pine persistent variables
    # ------------------------------------------------------------------

    belowos = np.zeros(n, dtype=bool)
    oscount = np.zeros(n, dtype=int)

    lastlowestrsi = np.full(n, np.nan, dtype=np.float64)
    lastlowestprice = np.full(n, np.nan, dtype=np.float64)
    lastlowestbi = np.full(n, -1, dtype=int)
    itsfineos = np.zeros(n, dtype=bool)

    maygoup = np.zeros(n, dtype=bool)

    aboveob = np.zeros(n, dtype=bool)
    obcount = np.zeros(n, dtype=int)

    lasthighestrsi = np.full(n, np.nan, dtype=np.float64)
    lasthighestprice = np.full(n, np.nan, dtype=np.float64)
    lasthighestbi = np.full(n, -1, dtype=int)
    itsfineob = np.zeros(n, dtype=bool)

    maygodown = np.zeros(n, dtype=bool)

    for i in range(n):

        # ==============================================================
        # BELOW OS
        # ==============================================================

        prev_belowos = belowos[i - 1] if i > 0 else False
        prev_rsi = rsi[i - 1] if i > 0 else np.nan
        current_rsi = rsi[i]

        if (
            not np.isnan(prev_rsi)
            and not np.isnan(current_rsi)
            and prev_rsi >= config.os
            and current_rsi < config.os
        ):
            belowos[i] = True

        elif (
            not np.isnan(current_rsi)
            and current_rsi > config.os
        ):
            belowos[i] = False

        else:
            belowos[i] = prev_belowos

        if belowos[i]:
            previous_count = oscount[i - 1] if i > 0 else 0
            oscount[i] = previous_count + 1

        else:
            oscount[i] = 0

        # Persistent variables inherit previous value
        if i > 0:
            lastlowestrsi[i] = lastlowestrsi[i - 1]
            lastlowestprice[i] = lastlowestprice[i - 1]
            lastlowestbi[i] = lastlowestbi[i - 1]
            itsfineos[i] = itsfineos[i - 1]

        # ==============================================================
        # EXITING OVERSOLD
        # ==============================================================

        if (
            i > 0
            and belowos[i - 1]
            and not belowos[i]
            and oscount[i - 1] > 0
        ):

            lastlowestrsi[i] = 101.0
            lastlowestbi[i] = i
            itsfineos[i] = True

            # IMPORTANT:
            # Pine loop:
            #
            # for x = 1 to oscount[1]
            #
            # if x > prd
            #     itsfineos := false
            #
            # if rsi[x] < lastlowestrsi
            #     ...
            #
            count = oscount[i - 1]

            for x in range(1, count + 1):

                if x > config.prd:
                    itsfineos[i] = False

                j = i - x

                if j < 0:
                    continue

                if (
                    not np.isnan(rsi[j])
                    and rsi[j] < lastlowestrsi[i]
                ):
                    lastlowestrsi[i] = rsi[j]
                    lastlowestbi[i] = j
                    lastlowestprice[i] = low[j]

            # ----------------------------------------------------------
            # EXACT Pine condition
            # ----------------------------------------------------------

            previous_low_rsi = (
                lastlowestrsi[i - 1]
                if i > 0 else np.nan
            )

            previous_low_price = (
                lastlowestprice[i - 1]
                if i > 0 else np.nan
            )

            previous_low_bi = (
                lastlowestbi[i - 1]
                if i > 0 else -1
            )

            change_last_low_rsi = (
                lastlowestrsi[i] - previous_low_rsi
                if (
                    not np.isnan(lastlowestrsi[i])
                    and not np.isnan(previous_low_rsi)
                )
                else np.nan
            )

            distance = (
                i - previous_low_bi
                if previous_low_bi >= 0
                else None
            )

            if (
                distance is not None
                and not np.isnan(change_last_low_rsi)
                and change_last_low_rsi != 0.0
                and lastlowestrsi[i] != 0.0
                and previous_low_rsi != 0.0
                and not np.isnan(previous_low_price)
                and lastlowestprice[i] < previous_low_price
                and distance < config.maxdis
                and itsfineos[i]
                and itsfineos[i - 1]
                and distance > config.mindis
            ):
                maygoup[i] = True

        # ==============================================================
        # ABOVE OB
        # ==============================================================

        prev_aboveob = aboveob[i - 1] if i > 0 else False

        if (
            i > 0
            and not np.isnan(prev_rsi)
            and not np.isnan(current_rsi)
            and prev_rsi <= config.ob
            and current_rsi > config.ob
        ):
            aboveob[i] = True

        elif (
            not np.isnan(current_rsi)
            and current_rsi < config.ob
        ):
            aboveob[i] = False

        else:
            aboveob[i] = prev_aboveob

        if aboveob[i]:
            previous_count = obcount[i - 1] if i > 0 else 0
            obcount[i] = previous_count + 1
        else:
            obcount[i] = 0

        if i > 0:
            lasthighestrsi[i] = lasthighestrsi[i - 1]
            lasthighestprice[i] = lasthighestprice[i - 1]
            lasthighestbi[i] = lasthighestbi[i - 1]
            itsfineob[i] = itsfineob[i - 1]

        # ==============================================================
        # EXITING OVERBOUGHT
        # ==============================================================

        if (
            i > 0
            and aboveob[i - 1]
            and not aboveob[i]
            and obcount[i - 1] > 0
        ):

            lasthighestrsi[i] = -1.0
            lasthighestbi[i] = i
            itsfineob[i] = True

            count = obcount[i - 1]

            for x in range(1, count + 1):

                if x > config.prd:
                    itsfineob[i] = False

                j = i - x

                if j < 0:
                    continue

                if (
                    not np.isnan(rsi[j])
                    and rsi[j] > lasthighestrsi[i]
                ):
                    lasthighestrsi[i] = rsi[j]
                    lasthighestbi[i] = j
                    lasthighestprice[i] = high[j]

            previous_high_rsi = (
                lasthighestrsi[i - 1]
                if i > 0 else np.nan
            )

            previous_high_price = (
                lasthighestprice[i - 1]
                if i > 0 else np.nan
            )

            previous_high_bi = (
                lasthighestbi[i - 1]
                if i > 0 else -1
            )

            change_last_high_rsi = (
                lasthighestrsi[i] - previous_high_rsi
                if (
                    not np.isnan(lasthighestrsi[i])
                    and not np.isnan(previous_high_rsi)
                )
                else np.nan
            )

            distance = (
                i - previous_high_bi
                if previous_high_bi >= 0
                else None
            )

            if (
                distance is not None
                and not np.isnan(change_last_high_rsi)
                and change_last_high_rsi != 0.0
                and lasthighestrsi[i] != 0.0
                and previous_high_rsi != 0.0
                and not np.isnan(previous_high_price)
                and lasthighestprice[i] > previous_high_price
                and distance < config.maxdis
                and itsfineob[i]
                and itsfineob[i - 1]
                and distance > config.mindis
            ):
                maygodown[i] = True

    data["maygoup"] = maygoup
    data["maygodown"] = maygodown

    # Store exact Pine coordinates for auditing.
    data["bottom_pivot_bar"] = np.where(
        maygoup,
        lastlowestbi,
        -1
    )

    data["top_pivot_bar"] = np.where(
        maygodown,
        lasthighestbi,
        -1
    )

    return data


def latest_signal(
    calculated: pd.DataFrame,
    max_age: int = 7,
) -> Optional[dict]:

    if len(calculated) == 0:
        return None

    current_bar = len(calculated) - 1

    bottom_indices = np.flatnonzero(
        calculated["maygoup"].to_numpy()
    )

    top_indices = np.flatnonzero(
        calculated["maygodown"].to_numpy()
    )

    candidates = []

    if len(bottom_indices):
        i = int(bottom_indices[-1])
        pivot = int(calculated.iloc[i]["bottom_pivot_bar"])

        if pivot >= 0:
            candidates.append(
                {
                    "type": "bottom",
                    "confirmation_bar": i,
                    "pivot_bar": pivot,
                }
            )

    if len(top_indices):
        i = int(top_indices[-1])
        pivot = int(calculated.iloc[i]["top_pivot_bar"])

        if pivot >= 0:
            candidates.append(
                {
                    "type": "top",
                    "confirmation_bar": i,
                    "pivot_bar": pivot,
                }
            )

    if not candidates:
        return None

    signal = max(
        candidates,
        key=lambda x: x["confirmation_bar"]
    )

    age = current_bar - signal["confirmation_bar"]

    if age > max_age:
        return None

    signal["age"] = age

    # User-facing candle offsets.
    signal["start_ago"] = current_bar - signal["pivot_bar"]
    signal["end_ago"] = current_bar - signal["confirmation_bar"]

    return signal
