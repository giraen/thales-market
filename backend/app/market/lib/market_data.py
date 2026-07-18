import yfinance as yf
import time
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta, timezone

from app.core.config import settings

def get_market_data(ticker: str, days: int = 365, fetch_peg: bool = True, _retrying: bool = False):
    try:
        client = StockHistoricalDataClient(settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        req_params = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start_time,
            end=end_time,
            feed=DataFeed.IEX
        )

        bars = client.get_stock_bars(req_params)
        df = bars.df

        if df is None or df.empty:
            return None, None
        
        df = df.droplevel(0) 
        df.rename(columns={
            "close": "Close", 
            "high": "High", 
            "low": "Low", 
            "open": "Open", 
            "volume": "Volume"
        }, inplace=True)

    except APIError as e:
        if "429" in str(e) and not _retrying:
            print(f"[RATE LIMIT] {ticker} hit Alpaca 429, waiting 5s and retrying once...")
            time.sleep(5)
            return get_market_data(ticker, days, fetch_peg, _retrying=True)
        print(f"Alpaca API Error: {e}")
        return None, None
    except Exception as e:
        print(f"Alpaca API Error: {e}")
        return None, None
    
    peg = None
    if fetch_peg:
        try:
            stock = yf.Ticker(ticker)
            peg = stock.info.get('pegRatio') or stock.info.get('trailingPegRatio')
        except Exception:
            peg = None

    return df, peg