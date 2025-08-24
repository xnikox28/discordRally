
#/comandos/grafica/utils.py

def fmt_price(p):
    if p is None:
        return "N/A"
    s = f"{p:.12f}".rstrip("0")
    return s[:-1] if s.endswith(".") else s

def fmt_pct(p):
    try:
        return f"{p:+.2f}%"
    except Exception:
        return "N/A"

def color_pct(p):
    try:
        if p is None:
            return 0x95a5a6  # gris
        return 0x2ecc71 if p >= 0 else 0xe74c3c  # verde / rojo
    except Exception:
        return 0x95a5a6

def trend_emoji_from(pct24, df):
    """
    1) Si %24h es fuerte (>= |0.5%|) decide por eso.
    2) Si no, usa posición vs EMA20 y su pendiente en el TF actual.
    """
    try:
        if pct24 is not None and abs(pct24) >= 0.5:
            return "📈" if pct24 >= 0 else "📉"

        c = df["close"]
        ema20 = c.ewm(span=20, adjust=False).mean()
        if len(ema20) < 3:
            return "⚪"

        price = float(c.iloc[-1])
        e = float(ema20.iloc[-1])
        slope = float(ema20.iloc[-1] - ema20.iloc[-3])

        if price > e and slope > 0:
            return "📈"
        if price < e and slope < 0:
            return "📉"
        return "⚪"
    except Exception:
        return "⚪"
