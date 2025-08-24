# comandos/zonas/__init__.py
from discord import app_commands, Interaction, Embed
from data_store import load_db, get_cfg
from comandos.grafica.render import fetch_ohlcv_df
from indicadores.core import compute_all_indicators
from indicadores.fib_pivots import intelligent_fib, classic_pivots_from_df_daily, build_zones_confluence
from comandos.grafica.utils import fmt_price
from datetime import datetime, timezone

MAX_TFS = 4
TOP_N   = 6

def setup(bot):
    @bot.tree.command(name="zonas", description="Zonas R/S inteligentes (FIB + Pivots + EMAs + Swings) por timeframe activo.")
    async def zonas(interaction: Interaction):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        symbol = cfg.get("symbol"); exchange = cfg.get("exchange")
        tfs = [tf.lower() for tf in (cfg.get("timeframes") or [])][:MAX_TFS]

        if not symbol or not exchange:
            return await interaction.response.send_message(
                "❗ Este canal no tiene símbolo/exchange configurados. Usa `/setcoin` primero.",
                ephemeral=True
            )

        if not tfs:
            tfs = ["4h", "1d", "1w"]

        await interaction.response.defer()

        embeds = []
        # Prepara pivots (día previo) una sola vez
        try:
            df1d = fetch_ohlcv_df(exchange, symbol, "1d", limit=30)
        except Exception as e:
            df1d = None

        for tf in tfs:
            try:
                df = fetch_ohlcv_df(exchange, symbol, tf, limit=300)
                df = compute_all_indicators(df)

                piv = None
                if df1d is not None:
                    piv = classic_pivots_from_df_daily(df1d)

                fib = intelligent_fib(df)  # usa rsi14/ema20/ema50 si existen
                zones = build_zones_confluence(df, fib, piv)[:TOP_N]

                emb = Embed(
                    title=f"🧭 Zonas clave — {tf.upper()}",
                    description=f"**{symbol}** en **{exchange}**",
                    color=0x8e44ad
                )
                if not zones:
                    emb.add_field(name="—", value="No se hallaron zonas relevantes.", inline=False)
                else:
                    for z in zones:
                        name = f"{'🟥 R' if z.kind=='R' else '🟩 S'}  {fmt_price(z.level)}"
                        tags = ", ".join(z.tags)
                        emb.add_field(
                            name=name,
                            value=f"score **{z.score:.2f}**  ·  {tags}",
                            inline=False
                        )
                emb.set_footer(text="Confluencia: FIB + Pivots + EMA + Swings")
                emb.timestamp = datetime.now(timezone.utc)
                embeds.append(emb)

            except Exception as e:
                err = Embed(title=f"⚠️ Error en {tf.upper()}", description=f"`{e}`", color=0xe67e22)
                embeds.append(err)

        await interaction.followup.send(embeds=embeds)
