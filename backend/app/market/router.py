from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/market", tags=["Market Analysis"])

@router.get("/analyze/{order}/{ticker}")
def analyze_stock(order: str, ticker: str):
    return {
        "message": f"This will run the pandas math for {ticker} looking for a {order} signal"
    }