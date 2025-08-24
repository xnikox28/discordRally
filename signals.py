import numpy as np
import pandas as pd

def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def rsi(close, n=14):
    delta = close.diff()
    up = delta.clip(lower=0)
    dn = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1/n, adjust=False).mean()
    roll_dn = dn.ewm(alpha=1/n, adjust=False).mean()
    rs = roll_up / (roll_dn.replace(0, np.nan))
    return 100 - (100 / (1 + rs))

def macd(close, f=12, s=26, sig=9):
    fast, slow = ema(close, f), ema(close, s)
    line = fast - slow
    signal = ema(line, sig)
    hist = line - signal
    return line, signal, hist

def wick_top_ratio(df):
    body_top = np.maximum(df['close'], df['open'])
    rng = (df['high'] - df['low']).replace(0, np.nan)
    return (df['high'] - body_top) / rng

def compute_indicators(df):
    df = df.copy()
    df['ema20'] = ema(df.close, 20)
    df['ema50'] = ema(df.close, 50)
    df['ema200'] = ema(df.close, 200)
    df['rsi'] = rsi(df.close, 14)
    df['macd'], df['macd_sig'], df['macd_hist'] = macd(df.close)
    df['vol_ma20'] = df.volume.rolling(20).mean()
    df['wick_top'] = wick_top_ratio(df)
    return df

def rally_signals(df, rsi_min=55, vol_mult=1.5):
    c = df.iloc[-1]
    p = df.iloc[-2]
    score, reasons = 0, []

    if c.close > c.ema50 > c.ema200:
        score += 1; reasons.append('Cierre > EMA50 > EMA200')
    if c.ema20 > c.ema50 and (c.ema20 - p.ema20) > 0 and (c.ema50 - p.ema50) > 0:
        score += 1; reasons.append('EMAs 20/50 ascendentes')
    if c.rsi >= rsi_min and c.rsi > p.rsi:
        score += 1; reasons.append(f'RSI fuerte {c.rsi:.1f}')
    if (c.macd > c.macd_sig) and (c.macd_hist > p.macd_hist):
        score += 1; reasons.append('MACD cruce/impulso')
    if c.volume > (c.vol_ma20 * vol_mult):
        score += 1; reasons.append('Volumen en spike')
    return score, reasons

def exit_signals(df, rsi_over=70):
    c = df.iloc[-1]
    p = df.iloc[-2]
    pp = df.iloc[-3]
    triggers = []
    if c.rsi >= rsi_over and c.rsi < p.rsi:
        triggers.append('RSI sale de sobrecompra')
    if (c.macd_hist < p.macd_hist < pp.macd_hist):
        triggers.append('MACD hist decreciente (3 velas)')
    if c.close < c.ema20:
        triggers.append('Cierre bajo EMA20')
    if (df['wick_top'].iloc[-1] > 0.6) or (df['wick_top'].iloc[-2] > 0.6):
        triggers.append('Mechas superiores largas')
    return triggers
