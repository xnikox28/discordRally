# ui.py
from discord import Embed

# ————— Utilidades —————
def enabled_badge(enabled: bool) -> str:
    return "🟢 Enabled" if enabled else "🔴 Disabled"

def color_enabled(enabled: bool) -> int:
    return 0x2ecc71 if enabled else 0xe74c3c  # verde / rojo

def fmt_price(p) -> str:
    if p is None:
        return "N/A"
    s = f"{p:.12f}".rstrip("0")
    return s[:-1] if s.endswith(".") else s

# ————— Embeds de ALERTAS —————
def make_rally_embed(symbol: str, exchange: str, timeframe: str,
                     price: float | None, rsi: float | None,
                     vol_mult: float | None, score: int | None):
    emb = Embed(
        title="🚀 ¡Alerta de Rally!",
        description=f"**{symbol}** en **{exchange}**",
        color=0x2ecc71
    )
    emb.add_field(name="⏱️ Timeframe", value=timeframe, inline=True)
    emb.add_field(name="💲 Precio", value=fmt_price(price), inline=True)
    if rsi is not None:
        emb.add_field(name="🧭 RSI", value=f"{rsi:.2f}", inline=True)
    if vol_mult is not None:
        emb.add_field(name="📈 Volumen", value=f"x{vol_mult:.2f}", inline=True)
    if score is not None:
        emb.add_field(name="⭐ Rally Score", value=str(score), inline=True)
    emb.set_footer(text="Señal temprana: evalúa tu plan de entrada y riesgo.")
    return emb

def make_correction_embed(symbol: str, exchange: str, timeframe: str,
                          price: float | None, rsi: float | None,
                          reason: str | None = None):
    emb = Embed(
        title="⚠️ Posible fin de Rally",
        description=f"**{symbol}** en **{exchange}**",
        color=0xe67e22  # naranja/alerta
    )
    emb.add_field(name="⏱️ Timeframe", value=timeframe, inline=True)
    emb.add_field(name="💲 Precio", value=fmt_price(price), inline=True)
    if rsi is not None:
        emb.add_field(name="🧭 RSI", value=f"{rsi:.2f}", inline=True)
    if reason:
        emb.add_field(name="🔍 Motivo", value=reason, inline=False)
    emb.set_footer(text="Considera asegurar ganancias / reducir exposición.")
    return emb

# ————— Embed de STATUS —————
def make_status_embed(cfg: dict, last_price: float | None):
    emb = Embed(
        title="📊 Estado del canal",
        description=enabled_badge(cfg.get("enabled", False)),
        color=color_enabled(cfg.get("enabled", False))
    )
    emb.add_field(name="🔗 Símbolo", value=cfg.get("symbol", "—"), inline=True)
    emb.add_field(name="🏦 Exchange", value=cfg.get("exchange", "—"), inline=True)
    emb.add_field(name="💲 Precio", value=fmt_price(last_price), inline=True)

    tfs = ", ".join(cfg.get("timeframes", [])) or "—"
    emb.add_field(name="⏱️ Timeframes", value=tfs, inline=True)

    emb.add_field(name="⭐ Rally Score min", value=str(cfg.get("rally_score_needed", "—")), inline=True)
    emb.add_field(
        name="🧭 RSI",
        value=f"rally ≥ {cfg.get('rsi_rally_min','—')} • salida < {cfg.get('rsi_exit_overbought','—')}",
        inline=True
    )
    emb.add_field(name="📈 Vol spike", value=f"x{cfg.get('vol_spike_mult','—')}", inline=True)
    emb.add_field(name="🧊 Cooloff", value=f"{cfg.get('cooloff_minutes','—')} min", inline=True)

    return emb
