from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.ledger import router as ledger_router
from app.market import router as market_router
from app.settings import router as settings_router
from app.watchlist import router as watchlist_router
from app.core.init_db import create_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield

app = FastAPI(title="Thales Market Signaler", lifespan=lifespan)

# Add routes
app.include_router(ledger_router.router)
app.include_router(market_router.router)
app.include_router(settings_router.router)
app.include_router(watchlist_router.router)

@app.get('/')
def check_status():
    return {"status": "ok"}