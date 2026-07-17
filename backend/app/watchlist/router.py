from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.rules import get_rules
from app.ledger.router import _resolve_asset

router = APIRouter(prefix="/api/v1/watchlist", tags=["Watchlist"])

class WatchlistAddRequest(BaseModel):
    ticker: str
    asset_class: str = "STOCK"

@router.get("")
def list_watchlist(user_id: str = Depends(get_current_user), conn = Depends(get_db)):
    """
    Gets all the tickers or assets the user wants to watch
    """
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, asset_class, added_at FROM watchlist WHERE user_id = %s ORDER BY added_at DESC", (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows

@router.post("")
def add_to_watchlist(
    payload: WatchlistAddRequest,
    user_id: str = Depends(get_current_user),
    conn = Depends(get_db)
):
    rules, ticker = _resolve_asset(payload.asset_class, payload.ticker)

    cursor = conn.cursor()
    try:
        # skip if ticker is already added to watchlist
        cursor.execute("""
            INSERT INTO watchlist (user_id, ticker, asset_class)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, ticker) DO NOTHING;
        """, (user_id, ticker, payload.asset_class))
        conn.commit()
        return {"status": "success", "ticker": ticker}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add to watchlist: {str(e)}")
    finally:
        cursor.close()

@router.delete("/{ticker}")
def remove_from_watchlist(ticker: str, user_id: str = Depends(get_current_user), conn = Depends(get_db)):
    """
    Remove a ticker from watchlist. 
    """
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM watchlist WHERE user_id = %s AND ticker = %s", (user_id, ticker.upper()))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove: {str(e)}")
    finally:
        cursor.close()