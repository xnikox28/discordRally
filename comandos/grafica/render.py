# comandos/grafica/render.py
import ccxt, pandas as pd
from datetime import datetime, timezone

def _exchange_of(name: str):
    ex = getattr(ccxt, name)()
    ex.load_markets()
    return ex

def fetch_ohlcv_df(exchange_name: str, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    ex = _exchange_of(exchange_name)
    if symbol not in ex.markets:
        raise ValueError(f"{exchange_name} no lista {symbol}")
    data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["ts","open","high","low","close","volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts")
    return df

def get_last_price(exchange_name: str, symbol: str) -> float | None:
    ex = _exchange_of(exchange_name)
    if symbol not in ex.markets:
        return None
    try:
        t = ex.fetch_ticker(symbol)
        return t.get("last")
    except Exception:
        return None

def get_change_24h_pct(exchange_name: str, symbol: str) -> float | None:
    """
    Intenta usar el 'percentage' de fetch_ticker (24h). Si no viene,
    calcula con 25 velas de 1h: (close[-1] / close[-25] - 1) * 100.
    """
    try:
        ex = _exchange_of(exchange_name)
        if symbol not in ex.markets:
            return None
        t = ex.fetch_ticker(symbol)  # muchos exchanges traen 'percentage' 24h aquí
        pct = t.get("percentage", None)
        if isinstance(pct, (int, float)):
            return float(pct)
    except Exception:
        pass

    # Fallback por velas
    try:
        df = fetch_ohlcv_df(exchange_name, symbol, "1h", limit=26)
        if len(df) >= 25:
            prev = float(df["close"].iloc[-25])
            now = float(df["close"].iloc[-1])
            if prev > 0:
                return (now / prev - 1.0) * 100.0
    except Exception:
        pass
    return None

def get_day_open_utc(exchange_name: str, symbol: str) -> float | None:
    # (se deja por si lo quieres usar en otro lado)
    df = fetch_ohlcv_df(exchange_name, symbol, "1d", limit=2)
    if df.empty:
        return None
    try:
        return float(df.iloc[-1].open)
    except Exception:
        return None

def render_png(df: pd.DataFrame, title: str) -> bytes:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        raise RuntimeError("Se requiere matplotlib para renderizar la gráfica (pip install matplotlib)") from e

    fig = plt.figure(figsize=(8.5, 4.8), dpi=130)
    ax = fig.add_subplot(111)

    ax.plot(df.index, df["close"])
    ax.set_title(title)
    ax.set_xlabel("Tiempo (UTC)")
    ax.set_ylabel("Precio")
    fig.autofmt_xdate()

    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
