import pandas_ta as ta
import numpy as np
import pandas as pd

class IndicatorEngine:
    def __init__(self, df: pd.DataFrame):
        # IMPROVEMENT 1: Deep copy prevents memory leak warnings in pandas
        self.df = df.copy()

    def add_all(self):
        self._add_vwap()
        self._add_rsi()
        self._add_bollinger()
        self._add_sma()
        self._add_obv()
        self._add_atr()
        self._add_garman_klass()
        self._add_zscore()
        return self.df
    
    def _add_vwap(self):
        self.df['VWAP'] = ta.vwap(self.df['High'], self.df['Low'], self.df['Close'], self.df['Volume'])

    def _add_rsi(self):
        self.df['RSI'] = ta.rsi(self.df['Close'], length=14)

    def _add_bollinger(self):
        bb = ta.bbands(self.df['Close'], length=20)
        if bb is not None:
            bb.rename(columns={
                bb.columns[0]: 'BBL', # Lower
                bb.columns[1]: 'BBM', # Mid
                bb.columns[2]: 'BBU'  # Upper
            }, inplace=True)
            self.df = pd.concat([self.df, bb], axis=1)

    def _add_sma(self):
        self.df['SMA_200'] = ta.sma(self.df['Close'], length=200)
        self.df['SMA_50'] = ta.sma(self.df['Close'], length=50)

    def _add_obv(self):
        self.df['OBV'] = ta.obv(self.df['Close'], self.df['Volume'])

    def _add_atr(self):
        self.df['ATR'] = ta.atr(self.df['High'], self.df['Low'], self.df['Close'], length=14)

    def _add_garman_klass(self):
        log_hl = np.log(self.df['High'] / self.df['Low']) ** 2
        log_co = np.log(self.df['Close'] / self.df['Open']) ** 2
        self.df['Garman_Klass'] = np.sqrt(0.5 * log_hl - (0.386 * log_co))

    def _add_zscore(self):
        mean = self.df['Close'].rolling(20).mean()
        std = self.df['Close'].rolling(20).std()
        self.df['Z_Score'] = (self.df['Close'] - mean) / std