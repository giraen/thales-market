from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger"])

@router.get("/balance")
def get_balance():
    return {"message": "This will return the $150 balance"}

@router.get("/positions")
def get_positions():
    return {"message": "This will return existing stocks"}

@router.post("/buy")
def log_buy():
    return {"message": "This will deduct cash and add shares"}
