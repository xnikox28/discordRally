# comandos/panel/blocks/SIETE_DIAS.py  (v4 — lista vertical simple, sin tiles ni sparkline)
from __future__ import annotations
from typing import Any, Iterable, List, Optional, Tuple
from PIL import ImageDraw, ImageFont

from data_store import load_db, get_cfg

# === CONFIG ===
CFG = {
    # Layout & paddings
    "pad": 14,
    "row_gap": 10,          # espacio vertical entre filas
    "row_inner_pad": 8,     # padding interno de cada mini-bloque invisible

    # Título centrado (independiente)
    "title_text": "ÚLTIMOS 7 DÍAS",  # puedes cambiarlo
    "font_title": 25,

    # Resumen 7D (izquierda, más grande e independiente)
    "show_summary": True,
    "summary_label": "7D",
    "font_summary": 15,

    # Filas: etiqueta de día a la izquierda, % a la derecha
    "font_day": 25,
    "font_pct": 22,           # punto de partida; luego auto-fit
    "pct_decimals": 2,        # se reduce dinámicamente si no cabe

    # Columnas y línea discontinua
    "min_dash_len": 16,       # longitud mínima de la línea discontinua
    "dash_len": 6,
    "dash_gap": 6,
    "dash_thickness": 1,
    "pct_col_max_ratio": 0.50,  # % máximo del ancho interno para la columna del %

    # Orden de días: arriba = hoy (True) o el más antiguo (False)
    "today_first": True,
}

# === Helpers de fuentes y dibujo ===
def _font(size=18):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()

_FONT_REG = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
]
_FONT_BOLD = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/seguisb.ttf",  # Segoe UI Semibold
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
]


def _font(size=18):
    for p in _FONT_REG:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()  # último recurso (fijo)


def _font_bold(size=18):
    for p in _FONT_BOLD:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return _font(size)

def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int,int]:
    box = draw.textbbox((0,0), text, font=font)
    return (box[2]-box[0], box[3]-box[1])

def _font_fit(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int, base: int, *, bold: bool=False) -> ImageFont.ImageFont:
    """Ajusta la fuente (binaria) para encajar en el rectángulo dado."""
    ff = _font_bold if bold else _font
    lo, hi = 8, 160
    best = ff(base)
    while lo <= hi:
        mid = (lo + hi)//2
        f = ff(mid)
        tw, th = _text_size(draw, text, f)
        if tw <= max_w and th <= max_h:
            best = f
            lo = mid + 1
        else:
            hi = mid - 1
    return best

def _draw_dashed(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, color: Tuple[int,int,int], thickness: int, seg: int, gap: int):
    if x2 <= x1 + 1:
        return
    x = x1
    while x < x2:
        x_end = min(x + seg, x2)
        draw.line([(x, y), (x_end, y)], fill=color, width=thickness)
        x = x_end + gap

# === Data helpers (reutilizamos tu lógica de 7 días) ===
try:
    from comandos.panel.data_adapter import get_daily_closes_8 as _get8
    ADAPTER_OK = True
except Exception:
    ADAPTER_OK = False
    _get8 = None  # type: ignore

try:
    from comandos.panel.coingecko_adapter import get_daily_closes_8_cg as _get8_cg
    _CG_OK = True
except Exception:
    _CG_OK = False
    _get8_cg = None  # type: ignore

try:
    from comandos.grafica.render import get_ohlcv as _get_ohlcv_render  # type: ignore
except Exception:
    _get_ohlcv_render = None  # type: ignore
try:
    from comandos.grafica.data import get_ohlcv as _get_ohlcv_data  # type: ignore
except Exception:
    _get_ohlcv_data = None  # type: ignore

AUTO_EX = ["BINANCE","KRAKEN","COINBASE","BYBIT","OKX","KUCOIN","BITSTAMP","GATE","BITGET","GEMINI","HUOBI"]
AUTO_Q = ["USD","USDT","USDC"]

def _split_symbol(sym: str) -> Tuple[str, Optional[str]]:
    if not sym:
        return ("SYMBOL", None)
    for sep in ("/",":","-"):
        if sep in sym:
            a,b = sym.split(sep,1)
            return (a.strip(), b.strip())
    up = sym.upper()
    for q in ("USDT","USDC","USD"):
        if up.endswith(q):
            return (up[:-len(q)], q)
    return (sym, None)

def _mk_variants(base: str, quote: Optional[str]) -> List[str]:
    base = base.strip().upper()
    if quote:
        return [f"{base}/{quote.strip().upper()}"]
    return [f"{base}/{q}" for q in AUTO_Q]

def _coerce_closes(raw: Iterable[Any]) -> List[float]:
    xs: List[float] = []
    for it in (raw or []):
        if it is None:
            continue
        if isinstance(it, dict):
            for k in ("close","c","Close","C","closing_price"):
                if k in it:
                    try:
                        xs.append(float(it[k])); break
                    except Exception: pass
        elif isinstance(it,(list,tuple)):
            try:
                if len(it)>=5: xs.append(float(it[4]))
                elif len(it)>=4: xs.append(float(it[3]))
            except Exception: pass
        else:
            try: xs.append(float(it))
            except Exception: pass
    return xs

def _try_ohlcv(fn, exchange: str, symbol: str, timeframe: str, limit: int):
    for tf in {timeframe, timeframe.lower(), timeframe.upper(), timeframe.capitalize()}:
        for ex in {exchange, exchange.lower(), exchange.upper()}:
            try:
                return fn(exchange=ex, symbol=symbol, timeframe=tf, limit=limit)  # type: ignore
            except Exception:
                try:
                    return fn(ex, symbol, tf, limit)  # type: ignore
                except Exception:
                    pass
    return None

def _get8_fallback(exchange: str, symbol: str) -> Optional[List[float]]:
    # 1d directo
    for fn in (f for f in (_get_ohlcv_render, _get_ohlcv_data) if f):
        raw = _try_ohlcv(fn, exchange, symbol, "1d", 9)
        xs = _coerce_closes(raw)
        if xs and len(xs)>=8: return xs[-8:]
    # 4h -> 6 velas/día
    for fn in (f for f in (_get_ohlcv_render, _get_ohlcv_data) if f):
        raw = _try_ohlcv(fn, exchange, symbol, "4h", 48)
        xs = _coerce_closes(raw)
        if xs and len(xs)>=48:
            days=[]; 
            for i in range(6, len(xs)+1, 6):
                days.append(xs[i-1])
                if len(days)>=8: break
            if len(days)>=8: return days[-8:]
    # 1h -> 24 velas/día
    for fn in (f for f in (_get_ohlcv_render, _get_ohlcv_data) if f):
        raw = _try_ohlcv(fn, exchange, symbol, "1h", 192)
        xs = _coerce_closes(raw)
        if xs and len(xs)>=192:
            days=[]
            for i in range(24, len(xs)+1, 24):
                days.append(xs[i-1])
                if len(days)>=8: break
            if len(days)>=8: return days[-8:]
    return None

def _get8_any(exchange: str, symbol: str) -> Optional[List[float]]:
    if ADAPTER_OK and _get8:
        xs = _get8(exchange, symbol)
        if xs and len(xs)>=8: return xs[-8:]
    return _get8_fallback(exchange, symbol)

def _autodiscover(symbol: str, exchange_hint: Optional[str]) -> Optional[List[float]]:
    base, quote = _split_symbol(symbol)
    vars = _mk_variants(base, quote)
    if exchange_hint:
        for sym in [symbol]+vars:
            xs = _get8_any(exchange_hint, sym)
            if xs and len(xs)>=8: return xs[-8:]
    for ex in AUTO_EX:
        if exchange_hint and ex.upper()==str(exchange_hint).upper():
            continue
        for sym in vars:
            xs = _get8_any(ex, sym)
            if xs and len(xs)>=8: return xs[-8:]
    try:
        if _CG_OK and _get8_cg:
            cg_closes, vs = _get8_cg(base, quote)
            if cg_closes and len(cg_closes)>=8:
                return cg_closes[-8:]
    except Exception:
        pass
    return None

def _pct(a: float, b: float) -> float:
    if b==0: return 0.0
    return a/b - 1.0

def _day_labels(today_first: bool) -> List[str]:
    import datetime as _dt
    names = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
    today = _dt.datetime.utcnow().date()
    days = [(today - _dt.timedelta(days=i)) for i in range(7)]  # hoy, ayer, ...
    labs = [names[d.weekday()] for d in days]
    return labs if today_first else list(reversed(labs))

# === RENDER ===
def render(draw: ImageDraw.ImageDraw, rect, theme, context):
    x, y, w, h = rect
    pad = CFG["pad"]
    inner_x = x + pad
    inner_y = y + pad
    inner_w = w - 2*pad

    db = load_db()
    cfg = get_cfg(db, context.get("guild_id"), context.get("channel_id"))
    symbol_cfg = (cfg or {}).get("symbol", "SYMBOL")
    exchange_cfg = ((cfg or {}).get("exchange") or None)

    closes = _autodiscover(symbol_cfg, exchange_cfg) or []

    if len(closes) < 8:
        # mensaje amigable si no hay datos
        f = _font(20)
        msg = "Sin datos"
        tw, th = _text_size(draw, msg, f)
        draw.text((x + (w-tw)//2, y + (h-th)//2), msg, fill=theme.get("muted", (160,160,160)), font=f)
        return

    # returns diarios (7)
    rets: List[float] = []
    for i in range(1,8):
        rets.append(_pct(closes[i], closes[i-1]))

    # ===== Top: 7D summary (izquierda) + Título centrado =====
    total = 1.0
    for r in rets: total *= (1.0 + r)
    agg = total - 1.0
    sum_txt = f"{CFG['summary_label']} {agg:+.{CFG['pct_decimals']}%}"
    f_sum = _font_bold(CFG["font_summary"])  # un poco más grande
    draw.text((inner_x, inner_y), sum_txt, fill=(46,204,113) if agg>=0 else (231,76,60), font=f_sum)
    _, sh = _text_size(draw, sum_txt, f_sum)

    # Título centrado
    f_title = _font_bold(CFG["font_title"])
    title = CFG["title_text"]
    tw, th = _text_size(draw, title, f_title)
    draw.text((x + (w - tw)//2, inner_y), title, fill=theme.get("text", (230,230,230)), font=f_title)

    cursor_y = inner_y + max(sh, th) + CFG["row_gap"] * 2

    # ===== Listado vertical de días =====
    labs = _day_labels(CFG["today_first"])  # 7

    f_day = _font_bold(CFG["font_day"])
    # --- Ajuste de espacio vertical para que la última fila toque el borde inferior ---
    row_pad = CFG["row_inner_pad"]
    base_gap = CFG["row_gap"]
    sample_pct_font = _font(CFG["font_pct"])

    row_heights = []
    for i in range(7):
        lbl = labs[i]
        h_day = _text_size(draw, lbl, f_day)[1]
        h_pct = _text_size(draw, "+100.00%", sample_pct_font)[1]
        row_heights.append(max(h_day, h_pct) + row_pad * 2)

    rows_total = sum(row_heights)
    gaps_total = base_gap * 6

    inner_bottom = y + h - pad
    planned_bottom = cursor_y + rows_total + gaps_total
    free = max(0, inner_bottom - planned_bottom)

    # Repartimos el espacio libre entre los 6 gaps (para empujar todo hacia abajo)
    extra_per_gap = free // 6 if free > 0 else 0
    extra_remainder = free % 6 if free > 0 else 0

    # columna derecha: ancho máximo disponible para %
    pct_col_max = int(inner_w * CFG["pct_col_max_ratio"])  # p.ej. 38% del rectángulo

    for i in range(7):
        idx = (len(rets) - 1 - i) if CFG["today_first"] else i
        r = rets[idx]
        day = labs[i]

        # fila invisible (para padding interno)
        row_h = max(_text_size(draw, day, f_day)[1], _text_size(draw, "+100.00%", _font(CFG["font_pct"]))[1]) + CFG["row_inner_pad"]*2
        row_y = cursor_y

        # etiqueta día (izquierda)
        dx = inner_x + CFG["row_inner_pad"]
        draw.text((dx, row_y + CFG["row_inner_pad"]), day, fill=theme.get("muted", (155,155,160)), font=f_day)
        dlw, dlh = _text_size(draw, day, f_day)

        # porcentaje (derecha, auto-fit dentro de columna derecha)
        pct_txt = f"{r:+.{CFG['pct_decimals']}%}"
        avail_h = row_h - CFG["row_inner_pad"]*2
        avail_w = min(pct_col_max, inner_w // 2)
        f_pct = _font_fit(draw, pct_txt, avail_w, avail_h, base=CFG["font_pct"], bold=True)
        pw, ph = _text_size(draw, pct_txt, f_pct)
        px = x + w - pad - CFG["row_inner_pad"] - pw
        py = row_y + (row_h - ph)//2
        draw.text((px, py), pct_txt, fill=(46,204,113) if r>=0 else (231,76,60), font=f_pct)

        # línea discontinua (entre fin de label y inicio del %)
        line_left = dx + dlw + 10
        line_right = px - 10
        if line_right - line_left >= CFG["min_dash_len"]:
            dash_col = theme.get("grid", (90,90,100))
            cy = row_y + row_h//2
            _draw_dashed(draw, line_left, cy, line_right, dash_col, CFG["dash_thickness"], CFG["dash_len"], CFG["dash_gap"])

        gap_extra = extra_per_gap + (1 if i < extra_remainder else 0)
        cursor_y += row_h + base_gap + gap_extra
