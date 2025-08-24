# indicadores/core.py
import pandas as pd

# ---------- Cálculos base ----------
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / roll_down
    return 100 - (100 / (1 + rs))

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

# ---------- Enriquecer un DF OHLCV ----------
def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Espera un DataFrame OHLCV con columnas: open, high, low, close, volume
    Index = timestamps (UTC). Devuelve el mismo DF con columnas extra:
      - ema20, ema50, ema100, ema200
      - rsi14
      - macd, macd_signal, macd_hist
    """
    c = df["close"].astype(float)
    df["ema20"] = ema(c, 20)
    df["ema50"] = ema(c, 50)
    df["ema100"] = ema(c, 100)
    df["ema200"] = ema(c, 200)
    df["rsi14"] = rsi(c, 14)
    macd_line, signal_line, hist = macd(c, 12, 26, 9)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = hist
    return df

def latest_values(df: pd.DataFrame) -> dict:
    """
    Devuelve un dict con el último valor de cada indicador principal.
    """
    row = df.iloc[-1]
    out = {
        "close": _f(row.get("close")),
        "volume": _f(row.get("volume")),
        "ema20": _f(row.get("ema20")),
        "ema50": _f(row.get("ema50")),
        "ema100": _f(row.get("ema100")),
        "ema200": _f(row.get("ema200")),
        "rsi14": _f(row.get("rsi14")),
        "macd": _f(row.get("macd")),
        "macd_signal": _f(row.get("macd_signal")),
        "macd_hist": _f(row.get("macd_hist")),
    }
    return out

def _f(x):
    try:
        return float(x) if pd.notna(x) else None
    except Exception:
        return None
