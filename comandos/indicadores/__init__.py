# comandos/indicadores/__init__.py
from discord import app_commands, Interaction, Embed
from data_store import load_db, get_cfg
from comandos.grafica.render import fetch_ohlcv_df  # reutilizamos tu fetch
from comandos.grafica.utils import fmt_price, fmt_pct, color_pct  # formateadores
from indicadores.core import compute_all_indicators, latest_values
from datetime import datetime, timezone

MAX_TFS = 5  # por si el canal tiene muchos timeframes

def setup(bot):
    @bot.tree.command(name="indicadores", description="Muestra RSI14, Volume, EMA20/50/100/200 y MACD para los timeframes activos.")
    async def indicadores(interaction: Interaction):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        symbol = cfg.get("symbol")
        exchange = cfg.get("exchange")
        tfs = [tf.lower() for tf in (cfg.get("timeframes") or [])][:MAX_TFS]

        if not symbol or not exchange:
            return await interaction.response.send_message(
                "❗ Este canal no tiene símbolo/exchange configurados. Usa `/setcoin` primero.",
                ephemeral=True
            )

        if not tfs:
            tfs = ["4h", "1d", "1w"]

        await interaction.response.defer(ephemeral=False)

        embeds = []
        for tf in tfs:
            try:
                df = fetch_ohlcv_df(exchange, symbol, tf, limit=300)
                df = compute_all_indicators(df)
                vals = latest_values(df)

                emb = Embed(
                    title=f"📊 Indicadores — {tf.upper()}",
                    description=f"**{symbol}** en **{exchange}**",
                    color=0x3498db
                )
                # precio y volumen
                emb.add_field(name="💲 Close", value=fmt_price(vals["close"]), inline=True)
                emb.add_field(name="📦 Vol", value=fmt_price(vals["volume"]), inline=True)
                emb.add_field(name="🧭 RSI(14)", value=(f"{vals['rsi14']:.2f}" if vals["rsi14"] is not None else "N/A"), inline=True)

                # EMAs
                emb.add_field(name="EMA20", value=(fmt_price(vals["ema20"])), inline=True)
                emb.add_field(name="EMA50", value=(fmt_price(vals["ema50"])), inline=True)
                emb.add_field(name="EMA100", value=(fmt_price(vals["ema100"])), inline=True)
                emb.add_field(name="EMA200", value=(fmt_price(vals["ema200"])), inline=True)

                # MACD
                macd_line = vals["macd"]
                macd_sig = vals["macd_signal"]
                macd_hist = vals["macd_hist"]
                macd_txt = (
                    f"line: {macd_line:.6f}\nsignal: {macd_sig:.6f}\nhist: {macd_hist:+.6f}"
                    if None not in (macd_line, macd_sig, macd_hist) else "N/A"
                )
                emb.add_field(name="📉 MACD (12,26,9)", value=macd_txt, inline=False)

                emb.set_footer(text="Actualizado")
                emb.timestamp = datetime.now(timezone.utc)
                embeds.append(emb)
            except Exception as e:
                err = Embed(
                    title=f"⚠️ Error {tf.upper()}",
                    description=f"`{e}`",
                    color=0xe67e22
                )
                embeds.append(err)

        # Discord recomienda enviar <= 10 embeds a la vez. Aquí son pocos.
        # Si prefieres, puedes unirlos en un solo embed con varias secciones.
        await interaction.followup.send(embeds=embeds)
