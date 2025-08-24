from discord import app_commands, Interaction
from data_store import load_db, get_cfg
import ccxt
from ui import make_status_embed  # 👈 usamos el helper nuevo

def _is_geoblocked(exc: Exception) -> bool:
    s = str(exc).lower()
    return "403" in s or "forbidden" in s or "cloudfront" in s

def setup(bot):
    @bot.tree.command(name="status", description="Muestra la configuración de ESTE canal.")
    async def status(interaction: Interaction):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)

        last_price = None
        try:
            ex = getattr(ccxt, cfg['exchange'])()
            ex.load_markets()
            if cfg['symbol'] in ex.markets:
                last_price = ex.fetch_ticker(cfg['symbol']).get("last")
        except Exception as e:
            # precio se queda en None; el embed ya mostrará N/A
            pass

        emb = make_status_embed(cfg, last_price)
        await interaction.response.send_message(embed=emb)
