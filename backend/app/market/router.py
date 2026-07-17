from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.ledger.service import get_position
from app.market.service import run_buy_analysis, run_sell_analysis, MarketDataUnavailable, InsufficientHistory

router = APIRouter(prefix="/api/v1/market", tags=["Market Analysis"])


@router.get("/analyze/buy/{ticker}")
def analyze_buy(ticker: str):
    ticker = ticker.upper()
    try:
        return run_buy_analysis(ticker)
    except MarketDataUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InsufficientHistory as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/analyze/sell/{ticker}")
def analyze_sell(
    ticker: str,
    entry_price: Optional[float] = Query(default=None, description="Override auto-lookup from your ledger"),
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    ticker = ticker.upper()
    resolved_entry_price = entry_price
    
    # No manual price given, then look up what the user actually paid, on average
    if resolved_entry_price is None:
        position = get_position(conn, user_id, ticker)
        if position["net_quantity"] <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"No open position in {ticker} to check."
            )
        resolved_entry_price = float(position["avg_entry_price"])

    try:
        return run_sell_analysis(ticker, resolved_entry_price)
    except MarketDataUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InsufficientHistory as e:
        raise HTTPException(status_code=422, detail=str(e))