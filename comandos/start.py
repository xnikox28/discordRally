from discord import app_commands, Interaction
from data_store import load_db, get_cfg, set_cfg
import monitor
import ccxt

def _is_geoblocked(exc: Exception) -> bool:
    s = str(exc).lower()
    return "403" in s or "forbidden" in s or "cloudfront" in s

def setup(bot):
    @bot.tree.command(name="start", description="Inicia el monitoreo en ESTE canal (con validación breve).")
    async def start(interaction: Interaction):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)

        symbol = (cfg.get("symbol") or "").strip().upper()
        exchange_name = (cfg.get("exchange") or "").strip().lower()

        if not symbol or not exchange_name:
            return await interaction.response.send_message(
                "❗ Este canal no tiene símbolo/exchange configurados.\n"
                "Usa: `/setcoin SYMBOL/QUOTE EXCHANGE` (ej. `/setcoin WIF/USDT binance`).",
                ephemeral=True
            )

        # Validación concisa del exchange y del par
        try:
            ex = getattr(ccxt, exchange_name)()
            ex.load_markets()
        except Exception:
            return await interaction.response.send_message(
                f"⚠️ Exchange **{exchange_name}** inválido o inaccesible. Prueba `binance`, `kraken`, `kucoin`.",
                ephemeral=True
            )

        if symbol not in ex.markets:
            return await interaction.response.send_message(
                f"⚠️ **{exchange_name}** no tiene **{symbol}**.\n"
                "Ejemplos: `/setcoin WIF/USD kraken`, `/setcoin WIF/USDT binance`, `/setcoin BONK/USDT kucoin`.",
                ephemeral=True
            )

        # Probar acceso (para detectar 403/CloudFront) sin spamear error largo
        try:
            ex.fetch_ticker(symbol)
        except Exception as e:
            if _is_geoblocked(e):
                return await interaction.response.send_message(
                    f"⚠️ Parece bloqueo regional en **{exchange_name}** (403/CloudFront). "
                    "Usa otro exchange como `binance`, `kraken` o `kucoin`, o corre el bot desde otra región.",
                    ephemeral=True
                )
            return await interaction.response.send_message(
                "⚠️ No se pudo iniciar por un error de red del exchange. Intenta nuevamente o cambia de exchange.",
                ephemeral=True
            )

        # Todo OK → activar y lanzar loop
        set_cfg(db, interaction.guild_id, interaction.channel_id, {"enabled": True})
        ok = monitor.start_channel(interaction.guild_id, interaction.channel_id)
        if ok:
            await interaction.response.send_message("🟢 Monitoreo **activado** para este canal.")
        else:
            await interaction.response.send_message("✅ Monitoreo ya estaba activo en este canal.")
