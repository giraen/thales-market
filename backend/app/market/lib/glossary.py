GLOSSARY = {
    "rsi": "Measures how fast and how much a price has moved recently, on a 0-100 scale. Above 70 usually signals overbought (may be due for a pullback); below 30 usually signals oversold (may be due for a bounce).",
    "vwap": "The average price this stock has traded at today, weighted by how much volume traded at each price. Price below VWAP can suggest a relative discount; above VWAP can suggest a relative premium.",
    "bb_lower": "The lower edge of the stock's normal recent price range (Bollinger Band). Price touching or dropping below this line suggests an unusually low price relative to recent volatility.",
    "bb_upper": "The upper edge of the stock's normal recent price range (Bollinger Band). Price touching or rising above this line suggests an unusually high price relative to recent volatility.",
    "sma_50": "The average closing price over the last 50 trading days. A common short/medium-term trend reference — price above it often suggests an uptrend, below often suggests a downtrend.",
    "sma_200": "The average closing price over the last 200 trading days. A common long-term trend reference — widely watched as a dividing line between a stock being in a broad uptrend or downtrend.",
    "peg_ratio": "Compares the stock's valuation (P/E ratio) to its expected earnings growth. Roughly: under 1 can suggest undervalued relative to growth, over 2.5 can suggest overvalued.",
    "atr": "Average True Range — the typical size of this stock's daily price swings recently, in dollars. Used here to size a reasonable stop-loss distance based on how volatile the stock actually is.",
    "stop_loss": "A suggested price at which to consider exiting, based on the stock's recent volatility (2x its ATR below the current price). Not a guarantee — just a volatility-aware reference point.",
}

def with_meaning(field_name: str, value):
    """Bundles a raw value with its glossary explanation, if one exists."""
    return {
        "value": value,
        "meaning": GLOSSARY.get(field_name)
    }