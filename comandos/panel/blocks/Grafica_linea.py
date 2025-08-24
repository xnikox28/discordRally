# comandos/panel/blocks/Grafica_linea.py
from PIL import ImageDraw, ImageFont

def _font(size=18):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except:
        return ImageFont.load_default()

def render(draw: ImageDraw.ImageDraw, rect, theme, context):
    x, y, w, h = rect
    title = "Grafica_linea"
    draw.text((x+16, y+12), title, fill=theme["text"], font=_font(20))
    # TODO: dibuja el contenido real aquí
