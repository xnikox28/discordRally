# comandos/panel/blocks/NOMBRE_CRYPTO_PRECIO.py
from __future__ import annotations

from typing import Optional

from PIL import ImageDraw, ImageFont

from comandos.grafica.render import get_change_24h_pct, get_last_price
from comandos.grafica.utils import fmt_pct, fmt_price
from data_store import get_cfg, load_db

# ================== CONFIGURABLE (edita a tu gusto) ==================
TITLE = {
    "font_size": 48,  # tamaño de "NOMBRE - PRECIO"
    "x": 16,  # offset X desde la esquina del bloque
    "y": 10,  # offset Y desde la esquina del bloque
    "uppercase": True,  # Forzar mayúsculas para el nombre
    "joiner": " - ",  # separador entre nombre y precio
}

SUB = {
    "font_size": 22,  # tamaño de "SYMBOL / EXCHANGE"
    "italic": True,  # usar cursiva si está disponible
    "x": 16,  # offset X absoluto
    "y": 65,  # offset Y absoluto (independiente del título)
}

RIGHT = {
    "label": "24H:",  # etiqueta
    "label_font": 48,  # tamaño del texto de etiqueta
    "pct_font": 48,  # tamaño del porcentaje
    "x_right": 150,  # margen derecho: distancia del borde derecho al bloque 24H
    "y": 10,  # offset Y absoluto del bloque 24H
    "show_bar": True,  # dibujar barra vertical separadora
    "bar_gap": 24,  # separación entre barra y bloque 24H
    "bar_extra_h": 6,  # altura extra (arriba/abajo) de la barra
    "align": "center",  # "top" o "center" (alineación vertical interna del % y etiqueta)
}
# =====================================================================


def _font(size=18):
    # Usa DejaVu (incluida con Pillow) para que escale bien. Fallbacks si no está.
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        for name in ("arial.ttf", "SegoeUI.ttf", "Arial.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()


def _font_italic(size=18):
    for name in ("DejaVuSans-Oblique.ttf", "ariali.ttf", "Arial Italic"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return _font(size)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    box = draw.textbbox((0, 0), text, font=font)
    return (box[2] - box[0], box[3] - box[1])


def _fmt_pct_str(pct: Optional[float]) -> str:
    if pct is None:
        return "N/A"
    try:
        return fmt_pct(pct)
    except Exception:
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct * 100:.2f}%"


def _fmt_price_str(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    try:
        return fmt_price(val)
    except Exception:
        return f"{val:.6f}" if val < 1 else f"{val:,.2f}"


def _derive_name(symbol: str) -> str:
    for sep in ("/", "-", ":"):
        if sep in symbol:
            return symbol.split(sep)[0]
    return symbol


def render(draw: ImageDraw.ImageDraw, rect, theme, context):
    x, y, w, h = rect

    guild_id = context.get("guild_id")
    channel_id = context.get("channel_id")

    db = load_db()
    cfg = get_cfg(db, guild_id, channel_id)

    symbol = (cfg or {}).get("symbol", "SYMBOL")
    exchange = (cfg or {}).get("exchange") or "EXCHANGE"
    name = (
        (cfg or {}).get("display_name")
        or (cfg or {}).get("symbol_name")
        or _derive_name(symbol)
    )
    display_name = name.upper() if TITLE.get("uppercase", False) else name

    # Datos de mercado (con fallback a exchange en minúsculas si aplica)
    last = None
    pct24 = None
    try:
        last = get_last_price(exchange, symbol)
    except Exception:
        try:
            last = get_last_price(str(exchange).lower(), symbol)
        except Exception:
            last = None
    try:
        pct24 = get_change_24h_pct(exchange, symbol)
    except Exception:
        try:
            pct24 = get_change_24h_pct(str(exchange).lower(), symbol)
        except Exception:
            pct24 = None

    # Colores
    text_col = theme["text"]
    muted_col = theme["muted"]
    green = (46, 204, 113)
    red = (231, 76, 60)
    pct_col = muted_col if pct24 is None else (green if pct24 >= 0 else red)

    # Fuentes
    f_title = _font(TITLE["font_size"])
    f_sub = (
        _font_italic(SUB["font_size"])
        if SUB.get("italic", False)
        else _font(SUB["font_size"])
    )
    f_lbl = _font(RIGHT["label_font"])
    f_pct = _font(RIGHT["pct_font"])

    # ------------------------------ TÍTULO (independiente) ------------------------------
    price_txt = _fmt_price_str(last)
    left_title = f"{display_name}{TITLE.get('joiner', ' - ')}{price_txt}"
    title_x = x + TITLE["x"]
    title_y = y + TITLE["y"]
    draw.text((title_x, title_y), left_title, fill=text_col, font=f_title)
    title_w, title_h = _text_size(draw, left_title, f_title)

    # ------------------------------ SUB (independiente) ---------------------------------
    sub_txt = f"{symbol} / {exchange.upper()}"
    sub_x = x + SUB["x"]
    sub_y = y + SUB["y"]
    draw.text((sub_x, sub_y), sub_txt, fill=muted_col, font=f_sub)

    # ------------------------------ DERECHA 24H (independiente) -------------------------
    lbl_txt = RIGHT["label"]
    pct_txt = _fmt_pct_str(pct24)

    lbl_w, lbl_h = _text_size(draw, lbl_txt, f_lbl)
    pct_w, pct_h = _text_size(draw, pct_txt, f_pct)

    total_right_w = lbl_w + 8 + pct_w
    right_x = x + w - RIGHT["x_right"] - total_right_w
    right_y = y + RIGHT["y"]

    # barra separadora
    if RIGHT.get("show_bar", True):
        bar_x = right_x - RIGHT.get("bar_gap", 24)
        extra = RIGHT.get("bar_extra_h", 6)
        draw.line(
            [(bar_x, right_y - extra), (bar_x, right_y + max(lbl_h, pct_h) + extra)],
            fill=theme["grid"],
            width=2,
        )

    # alineación vertical
    if RIGHT.get("align") == "center":
        max_h = max(lbl_h, pct_h)
        lbl_y = right_y + (max_h - lbl_h) // 2
        pct_y = right_y + (max_h - pct_h) // 2
    else:  # "top"
        lbl_y = right_y
        pct_y = right_y + (lbl_h - pct_h) // 2 if lbl_h > pct_h else right_y

    draw.text((right_x, lbl_y), lbl_txt, fill=text_col, font=f_lbl)
    draw.text((right_x + lbl_w + 8, pct_y), pct_txt, fill=pct_col, font=f_pct)
