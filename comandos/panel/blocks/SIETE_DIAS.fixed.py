# comandos/panel/blocks/SIETE_DIAS.py
from __future__ import annotations
from typing import Any, Iterable, List, Optional, Tuple
from PIL import ImageDraw, ImageFont

from data_store import load_db, get_cfg

# ---- Optional adapter (preferred) ----
try:
    from comandos.panel.data_adapter import get_daily_closes_8 as _get8
    ADAPTER_OK = True
except Exception:
    ADAPTER_OK = False
    _get8 = None  # type: ignore

# ---- CoinGecko fallback (last resort) ----
try:
    from comandos.panel.coingecko_adapter import get_daily_closes_8_cg as _get8_cg
    _CG_OK = True
except Exception:
    _CG_OK = False
    _get8_cg = None  # type: ignore

# ---- Fallbacks to existing OHLCV providers (kept for compatibility) ----
try:
    from comandos.grafica.render import get_ohlcv as _get_ohlcv_render  # type: ignore
except Exception:
    _get_ohlcv_render = None  # type: ignore
try:
    from comandos.grafica.data import get_ohlcv as _get_ohlcv_data  # type: ignore
except Exception:
    _get_ohlcv_data = None  # type: ignore

# ================== CONFIG ==================
CFG = {
    "title_prefix": "7D:",   # etiqueta del resumen
    "pad": 12,

    # rejilla de 7 tiles (se auto-ajustan para caber)
    "cell_w": 52,
    "cell_h": 34,
    "gap": 8,

    # % en cada tile (auto-fit, este es base)
    "font_pct": 18,
    "show_pct": True,

    # etiquetas de día
    "show_day_labels": True,
    "font_day": 12,

    # resumen (arriba-izquierda)
    "show_summary": True,
    "font_summary": 24,
    "grid_top_extra": 10,  # baja un poco los cuadros tras el resumen

    # sparkline inferior
    "spark_min_h": 30,

    # saturación de color para tiles
    "abs_cap": 0.15,

    # info de fuente (desactivada)
    "show_source": False,
    "font_source": 12,
}

AUTO = {
    "exchanges": ["BINANCE", "KRAKEN", "COINBASE", "BYBIT", "OKX", "KUCOIN", "BITSTAMP", "GATE", "BITGET", "GEMINI", "HUOBI"],
    "quotes": ["USD", "USDT", "USDC"],
}
# ============================================

# ----------------------- Fonts & utils -----------------------
def _font(size=18):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()

def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    box = draw.textbbox((0, 0), text, font=font)
    return (box[2] - box[0], box[3] - box[1])

def _font_fit(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, base: int = 18) -> ImageFont.ImageFont:
    """Devuelve una fuente que encaja en max_w x max_h usando búsqueda binaria."""
    lo, hi = 10, 96
    best = _font(base)
    while lo <= hi:
        mid = (lo + hi) // 2
        f = _font(mid)
        tw, th = _text_size(draw, text, f)
        if tw <= max_w and th <= max_h:
            best = f
            lo = mid + 1
        else:
            hi = mid - 1
    return best

def _day_labels_today_first() -> list:
    """Devuelve 7 etiquetas: izquierda=HOY, luego AYER, ..."""
    import datetime as _dt
    names = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
    today = _dt.datetime.utcnow().date()
    days = [(today - _dt.timedelta(days=i)) for i in range(7)]  # hoy, ayer, ...
    return [names[d.weekday()] for d in days]

def _autosize_grid(inner_w: int, cell_w: int, gap: int, n: int = 7) -> Tuple[int, int]:
    """Ajusta cell_w/gap para que n tiles quepan en inner_w sin overflow."""
    total = cell_w * n + gap * (n - 1)
    if total <= inner_w:
        # centrar con gap intacto
        return cell_w, gap
    # Reducir cell_w primero hasta un mínimo razonable, luego gap
    min_cell = 36
    min_gap = 4
    cw = cell_w
    gp = gap
    # Reduce mientras no quepa
    while cw > min_cell and cw * n + gp * (n - 1) > inner_w:
        cw -= 1
    while gp > min_gap and cw * n + gp * (n - 1) > inner_w:
        gp -= 1
    # Si todavía no cabe, forzar ajuste exacto distribuyendo espacio
    if cw * n + gp * (n - 1) > inner_w:
        cw = max(min_cell, (inner_w - gp * (n - 1)) // n)
        if cw * n + gp * (n - 1) > inner_w:
            gp = max(min_gap, (inner_w - cw * n) // (n - 1))
    return cw, gp

# ----------------------- Data helpers -----------------------
def _split_symbol(sym: str) -> Tuple[str, Optional[str]]:
    if not sym:
        return ("SYMBOL", None)
    for sep in ("/", ":", "-"):
        if sep in sym:
            a, b = sym.split(sep, 1)
            return (a.strip(), b.strip())
    up = sym.upper()
    for q in ("USDT", "USDC", "USD"):
        if up.endswith(q):
            return (up[:-len(q)], q)
    return (sym, None)

def _mk_symbol_variants(base: str, quote: Optional[str]) -> List[str]:
    base = base.strip().upper()
    if quote:
        return [f"{base}/{quote.strip().upper()}"]
    return [f"{base}/{q}" for q in AUTO["quotes"]]

def _coerce_closes(raw: Iterable[Any]) -> List[float]:
    closes: List[float] = []
    for it in (raw or []):
        if it is None:
            continue
        if isinstance(it, dict):
            for k in ("close", "c", "Close", "C", "closing_price"):
                if k in it:
                    try:
                        closes.append(float(it[k]))
                        break
                    except Exception:
                        pass
        elif isinstance(it, (list, tuple)):
            try:
                if len(it) >= 5:
                    closes.append(float(it[4]))
                elif len(it) >= 4:
                    closes.append(float(it[3]))
            except Exception:
                pass
        else:
            try:
                closes.append(float(it))
            except Exception:
                pass
    return closes

def _try_ohlcv(fn, exchange: str, symbol: str, timeframe: str, limit: int):
    for tf in {timeframe, timeframe.lower(), timeframe.upper(), timeframe.capitalize()}:
        for ex in {exchange, str(exchange).lower(), str(exchange).upper()}:
            for use_kwargs in (True, False):
                try:
                    if use_kwargs:
                        return fn(exchange=ex, symbol=symbol, timeframe=tf, limit=limit)  # type: ignore
                    else:
                        return fn(ex, symbol, tf, limit)  # type: ignore
                except Exception:
                    continue
    return None

def _get8_fallback(exchange: str, symbol: str) -> Optional[List[float]]:
    # 1d directo
    for fn in (f for f in (_get_ohlcv_render, _get_ohlcv_data) if f):
        raw = _try_ohlcv(fn, exchange, symbol, "1d", 9)
        xs = _coerce_closes(raw)
        if xs and len(xs) >= 8:
            return xs[-8:]
    # 4h -> 6 velas/día
    for fn in (f for f in (_get_ohlcv_render, _get_ohlcv_data) if f):
        raw = _try_ohlcv(fn, exchange, symbol, "4h", 48)
        xs = _coerce_closes(raw)
        if xs and len(xs) >= 48:
            days: List[float] = []
            for i in range(6, len(xs)+1, 6):
                days.append(xs[i-1])
                if len(days) >= 8:
                    break
            if len(days) >= 8:
                return days[-8:]
    # 1h -> 24 velas/día
    for fn in (f for f in (_get_ohlcv_render, _get_ohlcv_data) if f):
        raw = _try_ohlcv(fn, exchange, symbol, "1h", 192)
        xs = _coerce_closes(raw)
        if xs and len(xs) >= 192:
            days = []
            for i in range(24, len(xs)+1, 24):
                days.append(xs[i-1])
                if len(days) >= 8:
                    break
            if len(days) >= 8:
                return days[-8:]
    return None

def _get8_any(exchange: str, symbol: str) -> Optional[List[float]]:
    if ADAPTER_OK and _get8:
        xs = _get8(exchange, symbol)
        if xs and len(xs) >= 8:
            return xs[-8:]
    return _get8_fallback(exchange, symbol)

def _autodiscover_8(symbol: str, exchange_hint: Optional[str]) -> Tuple[Optional[List[float]], Optional[str], Optional[str]]:
    base, quote = _split_symbol(symbol)
    variants = _mk_symbol_variants(base, quote)

    # 1) hint primero
    if exchange_hint:
        for sym in [symbol] + variants:
            xs = _get8_any(exchange_hint, sym)
            if xs and len(xs) >= 8:
                return xs[-8:], exchange_hint, sym

    # 2) exchanges comunes
    for ex in AUTO["exchanges"]:
        if exchange_hint and ex.upper() == str(exchange_hint).upper():
            continue
        for sym in variants:
            xs = _get8_any(ex, sym)
            if xs and len(xs) >= 8:
                return xs[-8:], ex, sym

    return None, None, None

# ----------------------- Colors & sparkline -----------------------
def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b - 1.0

def _color_for_return(r: float, theme: dict) -> Tuple[int,int,int]:
    cap = max(0.001, float(CFG["abs_cap"]))
    r = max(-cap, min(cap, r)) / cap  # -> [-1, 1]
    neutral = (90, 95, 105) if sum(theme["panel"]) < 400 else (180, 185, 195)
    red = (231, 76, 60)
    green = (46, 204, 113)
    if r >= 0:
        t = r
        return (
            int(neutral[0] + (green[0]-neutral[0])*t),
            int(neutral[1] + (green[1]-neutral[1])*t),
            int(neutral[2] + (green[2]-neutral[2])*t),
        )
    else:
        t = -r
        return (
            int(neutral[0] + (red[0]-neutral[0])*t),
            int(neutral[1] + (red[1]-neutral[1])*t),
            int(neutral[2] + (red[2]-neutral[2])*t),
        )

def _text_contrast_color(bg: Tuple[int,int,int]) -> Tuple[int,int,int]:
    l = 0.2126*bg[0] + 0.7152*bg[1] + 0.0722*bg[2]
    return (20, 22, 24) if l > 160 else (240, 240, 240)

def _draw_sparkline(draw: ImageDraw.ImageDraw, rect, closes: list, theme: dict, *, positive: bool):
    x, y, w, h = rect
    if w <= 4 or h <= 4 or not closes or len(closes) < 2:
        return
    # Fondo sutil
    bg = (
        max(theme["panel"][0]-8,0),
        max(theme["panel"][1]-8,0),
        max(theme["panel"][2]-8,0),
    ) if sum(theme["panel"]) < 400 else (
        min(theme["panel"][0]+8,255),
        min(theme["panel"][1]+8,255),
        min(theme["panel"][2]+8,255),
    )
    draw.rectangle([x, y, x+w, y+h], fill=bg, outline=None)

    lo = min(closes); hi = max(closes); rng = (hi-lo) if hi>lo else 1.0
    n = len(closes)
    step = w / (n - 1)
    pts = []
    for i, v in enumerate(closes):
        px = int(x + i*step)
        py = int(y + h - ((v - lo)/rng)*h)
        pts.append((px, py))

    col = (46, 204, 113) if positive else (231, 76, 60)
    for i in range(1, len(pts)):
        draw.line([pts[i-1], pts[i]], fill=col, width=2)

# ----------------------------- RENDER -----------------------------
def render(draw: ImageDraw.ImageDraw, rect, theme, context):
    x, y, w, h = rect
    pad = CFG["pad"]

    db = load_db()
    cfg = get_cfg(db, context.get("guild_id"), context.get("channel_id"))
    symbol_cfg = (cfg or {}).get("symbol", "SYMBOL")
    exchange_cfg = ((cfg or {}).get("exchange") or None)

    closes: List[float] = []

    # 1) tu exchange + symbol
    xs, _, _ = _autodiscover_8(symbol_cfg, exchange_cfg)
    if xs and len(xs) >= 8:
        closes = xs[-8:]
    else:
        # 2) autodiscover sin hint
        xs, _, _ = _autodiscover_8(symbol_cfg, None)
        if xs and len(xs) >= 8:
            closes = xs[-8:]
        else:
            # 3) CoinGecko
            try:
                base, quote = _split_symbol(symbol_cfg)
                if _CG_OK and _get8_cg:
                    cg_closes, vs = _get8_cg(base, quote)
                    if cg_closes and len(cg_closes) >= 8:
                        closes = cg_closes[-8:]
            except Exception:
                pass

    # ---------- returns ----------
    rets: List[float] = []
    if closes and len(closes) >= 8:
        for i in range(1, 8):
            rets.append(_pct(closes[i], closes[i-1]))

    # ---------- summary on top-left ----------
    sum_f = _font(CFG["font_summary"])
    cx = x + pad
    cy = y + pad
    if CFG["show_summary"]:
        if rets:
            total = 1.0
            for r in rets:
                total *= (1.0 + r)
            agg = total - 1.0
            col = (46, 204, 113) if agg >= 0 else (231, 76, 60)
            sum_txt = f"{CFG['title_prefix']} {agg:+.2%}"
        else:
            col = theme["muted"]
            sum_txt = f"{CFG['title_prefix']} N/A"
        draw.text((cx, cy), sum_txt, fill=col, font=sum_f)
        tw, th = _text_size(draw, sum_txt, sum_f)
        cy += th + CFG["grid_top_extra"]

    # ---------- grid (auto-fit) ----------
    inner_w = w - 2*pad
    cell_w, gap = _autosize_grid(inner_w, CFG["cell_w"], CFG["gap"], n=7)
    cell_h = CFG["cell_h"]

    total_w = cell_w*7 + gap*6
    grid_x = x + pad + (inner_w - total_w)//2  # centrar dentro del área interna
    grid_y = cy

    days = _day_labels_today_first() if CFG["show_day_labels"] else None
    day_f = _font(CFG["font_day"]) if CFG["show_day_labels"] else None
    day_h = _text_size(draw, "Ag", day_f)[1] if day_f else 0

    for i in range(7):
        rx = grid_x + i*(cell_w + gap)
        ry = grid_y
        idx = len(rets) - 1 - i  # izquierda = hoy
        r = rets[idx] if 0 <= idx < len(rets) else 0.0

        bg = _color_for_return(r, theme)
        draw.rectangle([rx, ry, rx+cell_w, ry+cell_h], fill=bg, outline=theme["grid"])

        if CFG["show_pct"] and 0 <= idx < len(rets):
            txt = f"{r:+.1%}"
            f_pct = _font_fit(draw, txt, cell_w - 6, cell_h - 6, base=CFG["font_pct"])
            twp, thp = _text_size(draw, txt, f_pct)
            tx = rx + (cell_w - twp)//2
            ty = ry + (cell_h - thp)//2
            draw.text((tx, ty), txt, fill=_text_contrast_color(bg), font=f_pct)

        if days:
            lbl = days[i]  # [hoy, ayer, ...]
            lw, lh = _text_size(draw, lbl, day_f)
            ltx = rx + (cell_w - lw)//2
            lty = ry + cell_h + 2
            draw.text((ltx, lty), lbl, fill=theme["muted"], font=day_f)

    # ---------- sparkline (below) ----------
    spark_top = grid_y + cell_h + ((day_h + 4) if CFG["show_day_labels"] else 6)
    inner_bottom = y + h - pad
    spark_h = max(CFG["spark_min_h"], inner_bottom - spark_top)
    spark_rect = (x + pad, spark_top, inner_w, spark_h)
    if closes and len(closes) >= 2:
        agg_positive = False
        if rets:
            total = 1.0
            for r in rets:
                total *= (1.0 + r)
            agg_positive = (total - 1.0) >= 0
        _draw_sparkline(draw, spark_rect, closes[-8:], theme, positive=agg_positive)

    # fallback si no hay datos
    if not rets:
        msg = "Sin datos"
        mw, mh = _text_size(draw, msg, sum_f)
        draw.text((x + (w-mw)//2, y + (h-mh)//2), msg, fill=theme["muted"], font=sum_f)
