from __future__ import annotations

from datetime import datetime, timezone

import plotly.graph_objects as go
import streamlit as st

from data_feed import (
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    TRADINGVIEW_EXCHANGE,
    load_market_data,
)

from pine_rsi_tops_bottoms import (
    PineConfig,
    calculate_indicator,
    latest_signal,
)


st.set_page_config(
    page_title="RSI Tops and Bottoms",
    page_icon="📈",
    layout="wide",
)


# ============================================================
# Configuration
# ============================================================

CONFIG = PineConfig(
    length=14,
    source="close",
    ob=70,
    os=30,
    prd=10,
    mindis=5,
    maxdis=100,
)


# ============================================================
# Header
# ============================================================

st.title("RSI Tops and Bottoms — Pine v4 → Python")

st.caption(
    f"Symbol: {DEFAULT_SYMBOL} | "
    f"Timeframe: {DEFAULT_TIMEFRAME} | "
    f"TradingView exchange: {TRADINGVIEW_EXCHANGE}"
)


# ============================================================
# Refresh settings
# ============================================================

with st.sidebar:

    st.header("Settings")

    refresh_seconds = st.number_input(
        "Refresh interval (seconds)",
        min_value=10,
        max_value=300,
        value=30,
        step=10,
    )

    n_bars = st.number_input(
        "Historical bars",
        min_value=300,
        max_value=5000,
        value=5000,
        step=100,
    )

    st.markdown("---")

    st.write("Pine parameters")

    st.write(
        f"""
        RSI Length = {CONFIG.length}

        Upper Band = {CONFIG.ob}

        Lower Band = {CONFIG.os}

        Max OB/OS bars = {CONFIG.prd}

        Min distance = {CONFIG.mindis}

        Max distance = {CONFIG.maxdis}

        Signal validity = 7 candles
        """
    )


# ============================================================
# Live refresh
# ============================================================

@st.fragment(run_every=f"{int(refresh_seconds)}s")
def monitor():

    try:

        df, source = load_market_data(
            symbol=DEFAULT_SYMBOL,
            n_bars=int(n_bars),
        )

        calculated = calculate_indicator(
            df,
            CONFIG,
        )

        signal = latest_signal(
            calculated,
            max_age=7,
        )

    except Exception as exc:

        st.error(
            f"Data/Calculation error: {exc}"
        )

        return

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Data source",
        source,
    )

    c2.metric(
        "Bars",
        len(calculated),
    )

    c3.metric(
        "Last candle",
        calculated.iloc[-1]["timestamp"].strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
    )

    # --------------------------------------------------------
    # Signal
    # --------------------------------------------------------

    st.subheader("Latest signal")

    if signal is None:

        st.success(
            "سیگنال وجود ندارد."
        )

    else:

        start_ago = signal["start_ago"]
        end_ago = signal["end_ago"]

        if signal["type"] == "bottom":

            st.success(
                "همگرایی از کندل "
                f"{start_ago} قبلی شروع و در کندل "
                f"{end_ago} قبلی به پایان رسیده است."
            )

        elif signal["type"] == "top":

            st.error(
                "واگرایی از کندل "
                f"{start_ago} قبلی شروع و در کندل "
                f"{end_ago} قبلی به پایان رسیده است."
            )

        st.write(
            {
                "signal": signal["type"],
                "pivot_bar": signal["pivot_bar"],
                "confirmation_bar": signal["confirmation_bar"],
                "age": signal["age"],
                "start_ago": start_ago,
                "end_ago": end_ago,
            }
        )

    # --------------------------------------------------------
    # RSI chart
    # --------------------------------------------------------

    recent = calculated.tail(250)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=recent["timestamp"],
            y=recent["rsi"],
            mode="lines",
            name="RSI",
            line=dict(
                color="#8E1599",
                width=2,
            ),
        )
    )

    fig.add_hline(
        y=70,
        line_color="#808080",
        line_dash="dash",
    )

    fig.add_hline(
        y=30,
        line_color="#808080",
        line_dash="dash",
    )

    # --------------------------------------------------------
    # Draw latest bottom divergence
    # --------------------------------------------------------

    bottoms = calculated[
        calculated["maygoup"]
    ]

    if not bottoms.empty:

        row = bottoms.iloc[-1]

        pivot = int(
            row["bottom_pivot_bar"]
        )

        confirmation = int(
            bottoms.index[-1]
        )

        if pivot >= 0:

            p = calculated.iloc[pivot]
            c = calculated.iloc[confirmation]

            fig.add_trace(
                go.Scatter(
                    x=[
                        c["timestamp"],
                        p["timestamp"],
                    ],
                    y=[
                        c["rsi"],
                        p["rsi"],
                    ],
                    mode="lines+markers",
                    name="Bottom",
                    line=dict(
                        color="lime",
                        width=3,
                    ),
                )
            )

    # --------------------------------------------------------
    # Draw latest top divergence
    # --------------------------------------------------------

    tops = calculated[
        calculated["maygodown"]
    ]

    if not tops.empty:

        row = tops.iloc[-1]

        pivot = int(
            row["top_pivot_bar"]
        )

        confirmation = int(
            tops.index[-1]
        )

        if pivot >= 0:

            p = calculated.iloc[pivot]
            c = calculated.iloc[confirmation]

            fig.add_trace(
                go.Scatter(
                    x=[
                        c["timestamp"],
                        p["timestamp"],
                    ],
                    y=[
                        c["rsi"],
                        p["rsi"],
                    ],
                    mode="lines+markers",
                    name="Top",
                    line=dict(
                        color="red",
                        width=3,
                    ),
                )
            )

    fig.update_layout(
        height=500,
        yaxis=dict(
            range=[0, 100],
            title="RSI",
        ),
        xaxis_title="Time",
        hovermode="x unified",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


monitor()
