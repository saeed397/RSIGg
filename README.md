# RSI Tops and Bottoms — Pine Script to Python

Python implementation of the TradingView Pine Script indicator:

RSI Tops and Bottoms
by LonesomeTheBlue

The implementation follows the supplied Pine Script logic without
introducing an alternative divergence algorithm.

## Current Market

- Symbol: BTCUSDT
- Timeframe: 4H
- RSI Length: 14
- RSI Source: Close
- Upper Band: 70
- Lower Band: 30
- Max Number of Bars in OB/OS: 10
- Minimum Number of Bars Between Tops/Bottoms: 5
- Maximum Number of Bars Between Tops/Bottoms: 100
- Signal validity: 7 candles

## Important

The supplied Pine Script does not define an exchange.

Therefore, exact candle-by-candle equivalence depends on using the
same TradingView market/exchange that produced the original chart.

The current default exchange is:

BYBIT

This can be changed through:

TRADINGVIEW_EXCHANGE

environment variable.

## Signal Logic

### Bottom / Bullish Divergence

The original Pine Script requires:

1. RSI enters the oversold region.
2. The oversold sequence ends.
3. The lowest RSI value inside that sequence is identified.
4. The sequence must not exceed `prd = 10`.
5. A previous valid bottom must exist.
6. Current RSI bottom must be higher than the previous RSI bottom.
7. Current price low must be lower than the previous price low.
8. Distance must be greater than `mindis = 5`.
9. Distance must be less than `maxdis = 100`.
10. The signal is generated on the candle where the oversold
    condition ends.

### Top / Bearish Divergence

The original Pine Script requires:

1. RSI enters the overbought region.
2. The overbought sequence ends.
3. The highest RSI value inside that sequence is identified.
4. The sequence must not exceed `prd = 10`.
5. A previous valid top must exist.
6. Current RSI top must be lower than the previous RSI top.
7. Current price high must be higher than the previous price high.
8. Distance must be greater than `mindis = 5`.
9. Distance must be less than `maxdis = 100`.
10. The signal is generated on the candle where the overbought
    condition ends.

## RSI Calculation

The RSI is implemented directly rather than using pandas-ta.

The calculation follows the Wilder RMA structure used by TradingView/Pine.

RSI length:

14

Source:

Close

## Latest Signal Only

The application does not display the complete historical signal list.

Only the latest confirmed signal is considered.

If more than 7 candles have elapsed since the confirmation candle:

سیگنال وجود ندارد.

For a valid bottom:

همگرایی از کندل X قبلی شروع و در کندل Y قبلی به پایان رسیده است.

For a valid top:

واگرایی از کندل X قبلی شروع و در کندل Y قبلی به پایان رسیده است.

## Data Sources

### Primary

TradingView

### Fallback

Bybit

### Prohibited

Binance is not used anywhere in this project.

## TradingView Credentials

TradingView credentials should NOT be committed to GitHub.

For Streamlit Cloud, configure them through Streamlit Secrets.

Example:

TV_USERNAME = "YOUR_TRADINGVIEW_USERNAME"
TV_PASSWORD = "YOUR_TRADINGVIEW_PASSWORD"

## Local Installation

Create a virtual environment:

python -m venv .venv

Activate it.

Windows:

.venv\Scripts\activate

Linux/macOS:

source .venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Run:

streamlit run app.py

## Streamlit Deployment

1. Create a GitHub repository.
2. Upload all project files.
3. Open Streamlit Community Cloud.
4. Select the GitHub repository.
5. Set the main file to:

app.py

6. Add TradingView credentials through Streamlit Secrets if required.
7. Deploy.

## Project Structure

rsi_tops_bottoms/

├── README.md
├── app.py
├── data_feed.py
├── pine_rsi_tops_bottoms.py
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml.example

## Accuracy

This project is designed to reproduce the supplied Pine Script logic.

Exact candle-by-candle equivalence requires identical OHLC data.

Different exchanges may produce different:

- Open
- High
- Low
- Close
- Candle timestamps

Therefore, using data from a different exchange/feed can result in
different RSI values or divergence confirmation candles even when
the algorithm is identical.

For maximum verification accuracy, export the TradingView chart
data from the exact chart used by the Pine indicator and compare
the resulting RSI and signal bars against the Python implementation.

## Binance Restriction

No Binance API or Binance market-data endpoint is used by this project.

## Disclaimer

This software is an implementation/reproduction tool and is not
financial advice.

Always verify the generated signals against the original TradingView
indicator before using them for live trading.
