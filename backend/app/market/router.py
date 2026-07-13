from fastapi import APIRouter, HTTPException

from app.market.lib.market_data import get_market_data
from app.market.lib.indicators import IndicatorEngine
from app.market.lib.strategies import check_buy_signals

router = APIRouter(prefix="/api/v1/market", tags=["Market Analysis"])

@router.get("/analyze/buy/{ticker}")
def analyze_stock(ticker: str):
    ticker = ticker.upper()

    df, peg_ratio = get_market_data(ticker)
    if df is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch market data for {ticker}")

    if len(df) < 30:
        raise HTTPException(status_code=422, detail=f"Not enough price history for {ticker} to compute indicators")

    df_with_indicators = IndicatorEngine(df).add_all()
    result = check_buy_signals(df_with_indicators, peg_ratio)

    return {
        "ticker": ticker,
        "peg_ratio": peg_ratio,
        **result
    }

