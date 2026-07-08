from fastapi import FastAPI

from app.ledger import router as ledger_router
from app.market import router as market_router

app = FastAPI(title="Thales Market Signaler")

app.include_router(ledger_router.router)
app.include_router(market_router.router)

@app.get('/')
def check_status():
    return {"status": "ok"}

