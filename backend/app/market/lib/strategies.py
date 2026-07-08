import pandas as pd

def check_buy_signals(df, peg_ratio):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    stop_loss = latest['Close'] - (2 * latest['ATR'])
    response = {
        "decision": "WAIT",
        "reasons": [],
        "stop_loss": round(stop_loss, 2)
    }

    if peg_ratio is not None and peg_ratio > 2.5:
        response['reasons'].append(f"PEG Ratio too high ({peg_ratio})")
        return response
        
    if not pd.isna(latest['SMA_200']) and latest['Close'] < latest['SMA_200']:
        response['reasons'].append("Price is below 200 SMA (Downtrend)")
        return response

    if latest['Garman_Klass'] < 0.002: 
        response['reasons'].append("Low Volatility (Stock is sleeping)")
        return response
    
    avg_volatility = df['Garman_Klass'].rolling(30).mean().iloc[-1]
    if latest['Garman_Klass'] > (avg_volatility * 3):
        response['reasons'].append("Extreme Volatility (Market Panic). Wait.")
        return response

    score = 0
    ref_price = latest['VWAP'] if not pd.isna(latest['VWAP']) else latest['SMA_50']

    if latest['Close'] < ref_price:
        score += 1
        response['reasons'].append("Price below VWAP (Good Value)")
    
    if latest['RSI'] < 35:
        score += 1
        response['reasons'].append(f"RSI is Oversold ({round(latest['RSI'], 2)})")

    if 'BBL' in latest and latest['Close'] <= latest['BBL']:
        score += 1
        response['reasons'].append("Price touched Lower Bollinger Band")

    if latest['OBV'] > prev['OBV']:
        score += 1
        response['reasons'].append("OBV is rising (Volume supports move)")

    if latest['Z_Score'] < -2.0:
        score += 1
        response['reasons'].append(f"Deep Discount (Z-Score {round(latest['Z_Score'], 2)})")

    if score >= 2:
        response['decision'] = "BUY"

    return response


def check_sell_signals(df, entry_price, acceptable_loss: float = -0.10):
    latest = df.iloc[-1]
    current_price = latest['Close']

    response = {
        "decision": "HOLD",
        "action": "None",
        "reasons": []
    }

    if not entry_price:
        response['reasons'].append("No entry price provided. Analyzing technicals only.")
        if latest['Close'] < latest['SMA_50']:
             response['decision'] = "SELL"
             response['action'] = "SELL 100% (Trend Break)"
             response['reasons'].append("Price broke below 50 SMA")
        return response

    pct_gain = (current_price - entry_price) / entry_price

    # STOP LOSS: We now calculate against the dynamic variable
    if pct_gain < acceptable_loss:
        response['decision'] = "SELL"
        response['action'] = "SELL 100% (Stop Loss)"
        response['reasons'].append(f"Hit Max Loss ({acceptable_loss * 100}%). Current: {round(pct_gain*100, 2)}%")
        return response
    
    # PROFIT TAKING
    if pct_gain >= 0.50:
        response['decision'] = "SELL"
        response['action'] = "SELL 30% of Position"
        response['reasons'].append(f"Hit Profit Target 2 (+50%). Current: {round(pct_gain*100, 2)}%")
    elif pct_gain >= 0.20:
        response['decision'] = "SELL"
        response['action'] = "SELL 30% of Position"
        response['reasons'].append(f"Hit Profit Target 1 (+20%). Current: {round(pct_gain*100, 2)}%")

    if current_price < latest['SMA_50']:
        response['decision'] = "SELL"
        response['action'] = "SELL 100% (Trend Broken)"
        response['reasons'] = ["Trend broke (Price below 50 SMA). Exit all remaining positions."]
    
    if latest['RSI'] > 75 and response['decision'] == "HOLD":
        response['decision'] = "SELL"
        response['action'] = "SELL 10-20% (Snipe Top)"
        response['reasons'].append("RSI > 75 (Overbought). Consider trimming exposure.")

    return response