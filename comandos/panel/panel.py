# comandos/panel/panel.py
from __future__ import annotations
import io, os, importlib.util, json
from typing import Dict, Any
from PIL import Image, ImageDraw, ImageFont

# ===== Theming (dark=negro, light=blanco) =====
THEMES = {
    "dark": {  # negro
        "bg": (0, 0, 0),
        "panel": (14, 14, 16),
        "panel_alt": (8, 8, 10),   # más oscuro para efecto hundido
        "text": (245, 245, 245),
        "muted": (170, 170, 170),
        "accent": (99, 102, 241),
        "grid": (70, 70, 78),
        "hl": (70, 70, 78),       # highlight interno
        "sh": (10, 10, 12),       # sombra interna
    },
    "light": {  # blanco
        "bg": (255, 255, 255),
        "panel": (248, 249, 251),
        "panel_alt": (236, 238, 242),  # más oscuro que panel para hundido
        "text": (32, 33, 36),
        "muted": (115, 115, 115),
        "accent": (79, 70, 229),
        "grid": (150, 154, 164),  # contorno más visible que antes
        "hl": (255, 255, 255),
        "sh": (198, 202, 210),
    },
}

# ===== Layout =====
DEFAULT_LAYOUT = {
    "size": [1200, 700],
    "padding": 24,
    "gap": 16,
    "grid": {"cols": 12, "rows": 8},
    "areas": [
        ["HEADER", 0, 0, 12, 1],
        ["LEFT",   0, 1, 6, 5],
        ["RIGHT",  6, 1, 6, 5],
        ["FOOTER", 0, 6, 12, 2],
    ],
    "blocks": {
        "HEADER": "HEADER",
        "LEFT": "Indicadores",
        "RIGHT": "Alertas",
        "FOOTER": "Estado",
    },
}

BASE_DIR = os.path.dirname(__file__)
BLOCKS_DIR = os.path.join(BASE_DIR, "blocks")
LAYOUT_PATH = os.path.join(BASE_DIR, "layout.json")

def _load_layout() -> Dict[str, Any]:
    if os.path.exists(LAYOUT_PATH):
        with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_LAYOUT

def _load_block_renderer(name: str):
    path = os.path.join(BLOCKS_DIR, f"{name}.py")
    if not os.path.exists(path):
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"panel_block_{name}", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return getattr(mod, "render", None)

def _grid_to_px(area, size, padding, gap, grid_cols, grid_rows):
    W, H = size
    x, y, w, h = area[1], area[2], area[3], area[4]
    cell_w = (W - 2*padding - (grid_cols-1)*gap) / grid_cols
    cell_h = (H - 2*padding - (grid_rows-1)*gap) / grid_rows
    px = int(padding + x*cell_w + x*gap)
    py = int(padding + y*cell_h + y*gap)
    pw = int(w*cell_w + (w-1)*gap)
    ph = int(h*cell_h + (h-1)*gap)
    return (px, py, pw, ph)

def _rounded_rect(draw: ImageDraw.ImageDraw, xy, r, fill, outline=None, width=1):
    x, y, w, h = xy
    r = min(r, w//2, h//2)
    draw.rounded_rectangle([x, y, x+w, y+h], r, fill=fill, outline=outline, width=width)

def _inset_card(draw: ImageDraw.ImageDraw, xy, r, *, base_fill, hl, sh, outline=None, outline_w=2):
    # Base card (con contorno opcional)
    _rounded_rect(draw, xy, r, fill=base_fill, outline=outline, width=outline_w if outline else 0)
    x,y,w,h = xy
    # Inner highlight (top/left)
    draw.rounded_rectangle([x+2, y+2, x+w-2, y+h-2], r-2, outline=hl, width=1)
    # Inner shadow (bottom/right)
    draw.rounded_rectangle([x+3, y+3, x+w-3, y+h-3], r-3, outline=sh, width=1)

def _load_font(size=18):
    for name in ["Segoe UI", "Inter", "Arial", "DejaVuSans"]:
        try:
            return ImageFont.truetype(name, size)
        except:
            continue
    return ImageFont.load_default()

def render_panel_image(guild_id: int, channel_id: int, *, theme: str = "dark", borders: bool = True) -> bytes:
    theme = "dark" if theme not in THEMES else theme
    cfg = THEMES[theme]
    layout = _load_layout()

    size = tuple(layout.get("size", DEFAULT_LAYOUT["size"]))  # type: ignore
    padding = layout.get("padding", DEFAULT_LAYOUT["padding"])
    gap = layout.get("gap", DEFAULT_LAYOUT["gap"])
    grid = layout.get("grid", DEFAULT_LAYOUT["grid"])
    areas = layout.get("areas", DEFAULT_LAYOUT["areas"])
    blocks_map = layout.get("blocks", DEFAULT_LAYOUT["blocks"])

    img = Image.new("RGB", size, cfg["bg"])
    draw = ImageDraw.Draw(img)

    # Outer frame panel (opcional bordes)
    if borders:
        _rounded_rect(draw, (12, 12, size[0]-24, size[1]-24), r=24, fill=cfg["panel"], outline=cfg["grid"], width=2 if theme == "light" else 1)
    else:
        _rounded_rect(draw, (12, 12, size[0]-24, size[1]-24), r=24, fill=cfg["panel"], outline=None, width=0)

    # Shared context
    context = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "theme": theme,
        "borders": borders,
    }

    # Render each area
    for area in areas:
        name = area[0]
        rect = _grid_to_px(area, size, padding, gap, grid["cols"], grid["rows"])

        # Card styling
        if name in ("Grafica_linea", "RSI_MACD_VOLUME"):
            _inset_card(
                draw, rect, r=20,
                base_fill=cfg.get("panel_alt", cfg["panel"]),
                hl=cfg["hl"], sh=cfg["sh"],
                outline=cfg["grid"] if borders else None,
                outline_w=2 if theme == "light" else 1
            )
        else:
            outline_w = 2 if theme == "light" else 1
            _rounded_rect(draw, rect, r=20, fill=cfg["panel"], outline=(cfg["grid"] if borders else None), width=(outline_w if borders else 0))

        block_name = blocks_map.get(name)
        renderer = _load_block_renderer(block_name) if block_name else None

        if renderer is None:
            _render_placeholder(draw, rect, f"{name} • {block_name or 'N/A'}", cfg)
        else:
            try:
                renderer(draw, rect, cfg, context)
            except Exception as e:
                _render_error(draw, rect, f"{name}: {block_name}\n{e}", cfg)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def _render_placeholder(draw, rect, text, cfg):
    x, y, w, h = rect
    font = _load_font(18)
    draw.text((x+16, y+14), text, font=font, fill=cfg["muted"])

def _render_error(draw, rect, text, cfg):
    x, y, w, h = rect
    font = _load_font(16)
    draw.text((x+16, y+14), f"⚠️ {text}", font=font, fill=(220, 60, 60))
