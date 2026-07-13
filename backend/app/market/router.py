from fastapi import APIRouter, HTTPException, Depends, Query
from decimal import Decimal
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.market.lib.market_data import get_market_data
from app.market.lib.indicators import IndicatorEngine
from app.market.lib.strategies import check_buy_signals, check_sell_signals

router = APIRouter(prefix="/api/v1/market", tags=["Market Analysis"])

@router.get("/analyze/buy/{ticker}")
def analyze_buy(ticker: str):
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

@router.get("/analyze/sell/{ticker}")
def analyze_sell(
    ticker: str,
    entry_price: Optional[float] = Query(default=None, description="Override auto-lookup from your ledger"),
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    ticker = ticker.upper()

    resolved_entry_price = entry_price
    if resolved_entry_price is None:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE -quantity END) AS net_quantity,
                SUM(CASE WHEN transaction_type = 'BUY' THEN total_cost_basis ELSE -total_cost_basis END) AS net_cost
            FROM transaction_ledger
            WHERE user_id = %s AND ticker = %s
        """, (user_id, ticker))
        row = cursor.fetchone()
        cursor.close()

        net_qty = Decimal(str(row['net_quantity'])) if row and row['net_quantity'] else Decimal('0')
        net_cost = Decimal(str(row['net_cost'])) if row and row['net_cost'] else Decimal('0')

        if net_qty <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"No open position in {ticker} to check. Pass ?entry_price= for a hypothetical check."
            )

        resolved_entry_price = float(net_cost / net_qty)

    df, _ = get_market_data(ticker)
    if df is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch market data for {ticker}")

    if len(df) < 30:
        raise HTTPException(status_code=422, detail=f"Not enough price history for {ticker} to compute indicators")

    df_with_indicators = IndicatorEngine(df).add_all()
    result = check_sell_signals(df_with_indicators, resolved_entry_price)

    return {
        "ticker": ticker,
        "entry_price_used": resolved_entry_price,
        **result
    }