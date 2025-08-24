# comandos/info/__init__.py
from discord import app_commands, Interaction, Embed
from data_store import load_db, get_cfg
from comandos.grafica.render import get_last_price, get_change_24h_pct
from comandos.grafica.utils import fmt_price, fmt_pct, color_pct
from .view import InfoView
from .metrics import compute_volatility_24h, refine_params_by_vol
from datetime import datetime, timezone

def _recommend_by_price(last_price: float | None) -> tuple[float, float, str]:
    if last_price is None:
        return (0.05, 0.004, "indeterminado (fallback)")
    p = float(last_price)
    if p < 0.01:
        return (0.06, 0.006, "memecoin ultra barata")
    elif p < 1:
        return (0.05, 0.004, "altcoin mediana")
    else:
        return (0.03, 0.002, "major / alta capitalización")

def setup(bot):
    @bot.tree.command(
        name="info",
        description="Recomendaciones de parámetros (zigzag/tolerancia) + 24H cambio/volatilidad, según el par activo.",
    )
    async def info(interaction: Interaction):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        symbol = cfg.get("symbol"); exchange = cfg.get("exchange")

        if not symbol or not exchange:
            return await interaction.response.send_message(
                "❗ Este canal no tiene símbolo/exchange configurados. Usa `/setcoin` primero.",
                ephemeral=True
            )

        await interaction.response.defer()

        # Datos de mercado
        last = get_last_price(exchange, symbol)
        pct24 = get_change_24h_pct(exchange, symbol)
        sigma24, range24 = compute_volatility_24h(exchange, symbol)

        # Base por precio y refinamiento por volatilidad
        base_zz, base_tol, tier = _recommend_by_price(last)
        rec_zz, rec_tol, vol_tier = refine_params_by_vol(base_zz, base_tol, sigma24, range24)

        # 4) ¿Hay preset aplicado actualmente en el canal?
        has_applied = ("zigzag_pct" in cfg) or ("price_tolerance" in cfg)

        # Embed
        emb = Embed(
            title="ℹ️ Info del par y recomendaciones",
            description=f"**{symbol}** en **{exchange}**",
            color=color_pct(pct24),
            timestamp=datetime.now(timezone.utc),
        )

        # 1) Precio & Cambio
        emb.add_field(name="💲 Precio", value=fmt_price(last), inline=True)
        emb.add_field(name="📈 24H", value=fmt_pct(pct24), inline=True)
        emb.add_field(name="\u200b", value="\u200b", inline=True)

        # 2) Volatilidad
        vol_txt = (
            f"σ(1h) 24H: **{fmt_pct(sigma24)}**\n"
            f"Rango 24H: **{fmt_pct(range24)}**"
        )
        emb.add_field(name="🌪️ Volatilidad", value=vol_txt, inline=True)
        emb.add_field(name="🎯 Perfil precio", value=tier, inline=True)
        emb.add_field(name="🌡️ Perfil vol", value=vol_tier, inline=True)

        # 3) Recomendaciones
        emb.add_field(name="\u200b", value="\u200b", inline=True)
        emb.add_field(name="📐 zigzag_pct", value=f"**{rec_zz:.3f}**  (~{rec_zz*100:.1f}%)", inline=True)
        emb.add_field(name="🧲 tolerance", value=f"**{rec_tol:.3f}**  (~{rec_tol*100:.1f}%)", inline=True)

        emb.add_field(
            name="📝 Guía rápida",
            value=(
                "• **Majors (≥ $1)**: zigzag ~3% · tol ~0.2%\n"
                "• **Altcoins ($0.01–$1)**: zigzag ~5% · tol ~0.4%\n"
                "• **Memecoins (< $0.01)**: zigzag ~6% · tol ~0.6%\n"
                "• **Sube** ambos si la vol es alta; **baja** si es muy baja.\n"
            ),
            inline=False,
        )

        # 4) ⚙️ Mostrar qué parámetros están APLICADOS en este canal
        applied_zz  = float(cfg.get("zigzag_pct", rec_zz))
        applied_tol = float(cfg.get("price_tolerance", rec_tol))
        emb.add_field(
            name="⚙️ Parámetros aplicados en este canal",
            value=(
                f"Zigzag_pct aplicado: **{applied_zz:.3f}**  (~{applied_zz*100:.1f}%)\n"
                f"Price_tolerance aplicado: **{applied_tol:.3f}**  (~{applied_tol*100:.1f}%)"
            ),
            inline=False
        )

        view = InfoView(
            symbol=symbol, exchange=exchange,
            last=last, pct24=pct24,
            sigma24=sigma24, range24=range24,
            tier_price=tier, tier_vol=vol_tier,
            rec_zz=rec_zz, rec_tol=rec_tol,
            has_applied=has_applied,   # 👈 FIX: pasamos el flag requerido
        )
        await interaction.followup.send(embed=emb, view=view)
