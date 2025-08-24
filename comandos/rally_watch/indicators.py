import numpy as np
import pandas as pd

def ema(s, n): 
    return s.ewm(span=n, adjust=False).mean()

def atr(df, n=14):
    h,l,c = df['high'], df['low'], df['close']
    prev_c = c.shift(1)
    tr = pd.concat([(h-l).abs(), (h-prev_c).abs(), (l-prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def rsi_fast(close, period=5):
    d = close.diff()
    up = np.where(d>0, d, 0.0)
    dn = np.where(d<0, -d, 0.0)
    au = pd.Series(up, index=close.index).rolling(period).mean()
    ad = pd.Series(dn, index=close.index).rolling(period).mean()
    rs = au / ad.replace(0, np.nan)
    rsi = 100 - (100/(1+rs))
    return rsi.bfill().fillna(50)


def keltner(df, ema_len=20, atr_len=14, mult=1.5):
    mid = ema(df['close'], ema_len)
    rng = atr(df, atr_len) * mult
    upper = mid + rng
    lower = mid - rng
    return mid, upper, lower

def slope(x, lb=5): 
    return (x - x.shift(lb)) / lb

def last_swing_low(df, lookback=12):
    lows = df['low']
    pivL = (lows.shift(1) > lows) & (lows.shift(-1) > lows)
    sw = lows[pivL].tail(3)
    return float(sw.iloc[-1]) if len(sw) else float(lows.tail(lookback).min())
