# comandos/grafica/__init__.py
from discord import app_commands, Interaction, File, Embed
from data_store import load_db, get_cfg
from .render import fetch_ohlcv_df, render_png, get_last_price, get_change_24h_pct
from .view import GraficaView
from .utils import fmt_price, fmt_pct, color_pct, trend_emoji_from  # ← import utilidades
import io, time
from datetime import datetime, timezone

def setup(bot):
    @bot.tree.command(name="grafica", description="Muestra una gráfica del símbolo activo con botones de timeframes.")
    async def grafica(interaction: Interaction):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        symbol = cfg.get("symbol")
        exchange = cfg.get("exchange")
        cfg_tfs = [tf.lower() for tf in (cfg.get("timeframes") or [])]

        if not symbol or not exchange:
            return await interaction.response.send_message(
                "❗ Este canal no tiene símbolo/exchange configurados. Usa `/setcoin` primero.",
                ephemeral=True
            )

        await interaction.response.defer()  # evita 10062

        start_tf = cfg_tfs[0] if cfg_tfs else "4h"

        try:
            df = fetch_ohlcv_df(exchange, symbol, start_tf, limit=200)
            png = render_png(df, title=f"{symbol} @ {exchange.upper()}  •  {start_tf.upper()}")
        except Exception as e:
            return await interaction.followup.send(f"⚠️ No pude generar la gráfica: `{e}`", ephemeral=True)

        last = get_last_price(exchange, symbol)
        pct24 = get_change_24h_pct(exchange, symbol)

        fname = f"chart_{int(time.time())}.png"
        file = File(io.BytesIO(png), filename=fname)

        emb = Embed(title="📈 Gráfica", color=color_pct(pct24))
        emb.description = (
            f"**{symbol}** en **{exchange}**  •  TF **{start_tf.upper()}**\n"
            f"**Precio:** {fmt_price(last)}   •   **24H:** {fmt_pct(pct24)}"
        )
        emb.set_image(url=f"attachment://{fname}")
        emb.timestamp = datetime.now(timezone.utc)
        emb.set_footer(text=f"{trend_emoji_from(pct24, df)} • actualizado")

        view = GraficaView(symbol=symbol, exchange=exchange, timeframes=cfg_tfs, current_tf=start_tf)
        await interaction.followup.send(embed=emb, file=file, view=view)
