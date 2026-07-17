import pandas as pd

from app.market.lib.market_data import get_market_data
from app.market.lib.indicators import IndicatorEngine
from app.market.lib.strategies import check_buy_signals, check_sell_signals
from app.market.lib.glossary import with_meaning

class MarketDataUnavailable(Exception):
    pass

class InsufficientHistory(Exception):
    pass


def _safe_round(value, digits=2):
    # NaN shows up when there isn't enough price history for an indicator
    # (e.g. SMA_200 on a stock younger than 200 trading days).
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _build_snapshot(df, peg_ratio=None):
    """Takes the latest row of computed indicators and formats it for display."""
    latest = df.iloc[-1]

    stop_loss_value = _safe_round(latest['Close'] - (2 * latest['ATR'])) if not pd.isna(latest['ATR']) else None

    return {
        "price": _safe_round(latest['Close']),
        "risk_data": {
            "stop_loss": with_meaning("stop_loss", stop_loss_value),
            "atr": with_meaning("atr", _safe_round(latest['ATR'])),
        },
        "indicators": {
            "rsi": with_meaning("rsi", _safe_round(latest['RSI'])),
            "vwap": with_meaning("vwap", _safe_round(latest['VWAP'])),
            "bb_lower": with_meaning("bb_lower", _safe_round(latest.get('BBL'))),
            "bb_upper": with_meaning("bb_upper", _safe_round(latest.get('BBU'))),
            "sma_50": with_meaning("sma_50", _safe_round(latest['SMA_50'])),
            "sma_200": with_meaning("sma_200", _safe_round(latest['SMA_200'])),
            "peg_ratio": with_meaning("peg_ratio", _safe_round(peg_ratio) if peg_ratio is not None else None),
        },
        "last_updated": str(df.index[-1]),
    }


def get_market_snapshot(ticker: str):
    """
    Fetches price history for a ticker and runs every indicator on it.
    Raises instead of returning None/error codes, since callers (a route,
    or later the scan job) each handle failure differently — a route
    turns this into a 404/422, the scan job will just skip the ticker.
    """

    # gets the market data
    df, peg_ratio = get_market_data(ticker)
    if df is None:
        raise MarketDataUnavailable(f"Could not fetch market data for {ticker}")
    
    # too little history
    if len(df) < 30:
        raise InsufficientHistory(f"Not enough price history for {ticker} to compute indicators")

    # adds the indicators in the df
    df_with_indicators = IndicatorEngine(df).add_all()
    return df_with_indicators, peg_ratio


def run_buy_analysis(ticker: str) -> dict:
    # get the market data with indicators
    df, peg_ratio = get_market_snapshot(ticker)

    # runs the analysis for the current market data based on the indicators
    result = check_buy_signals(df, peg_ratio)

    return {
        "ticker": ticker,
        "order": "BUY",
        "decision": result['decision'],
        "action": result.get('action', 'N/A'),
        "reasons": result['reasons'],
        **_build_snapshot(df, peg_ratio)
    }


def run_sell_analysis(ticker: str, entry_price: float) -> dict:
    # get the market data with indicators
    df, _ = get_market_snapshot(ticker)

    # runs the analysis for the current market data based on the indicators
    result = check_sell_signals(df, entry_price)

    return {
        "ticker": ticker,
        "order": "SELL",
        "entry_price_used": round(entry_price, 2),
        "decision": result['decision'],
        "action": result.get('action', 'N/A'),
        "reasons": result['reasons'],
        **_build_snapshot(df)
    }