from discord import app_commands, Interaction
from data_store import load_db, set_cfg
import ccxt

PREFERRED_QUOTES = ["USDT", "USD"]  # preferencia: primero USDT, luego USD

def _is_geoblocked(exc: Exception) -> bool:
    s = str(exc).lower()
    return "403" in s or "forbidden" in s or "cloudfront" in s

def _auto_pick_symbol(ex, base_upper: str):
    """
    Devuelve (symbol_elegido, fue_auto, sugerencia_txt)
    - symbol_elegido: str o None
    - fue_auto: bool (True si se eligió automáticamente)
    - sugerencia_txt: texto con alternativas si no se pudo elegir
    """
    # Buscar todos los mercados que tengan esa base
    candidates = [m for m in ex.markets.values() if m.get("base", "").upper() == base_upper]
    if not candidates:
        return None, False, f"No encontré mercados con base **{base_upper}** en **{ex.id}**."

    # Intentar por preferencia de QUOTE (USDT -> USD)
    for quote in PREFERRED_QUOTES:
        # Primero activos
        active = [m for m in candidates if m.get("quote", "").upper() == quote and m.get("active", True)]
        if active:
            return active[0]["symbol"], True, ""
        # Si no hay activos, cualquiera con ese quote
        anyq = [m for m in candidates if m.get("quote", "").upper() == quote]
        if anyq:
            return anyq[0]["symbol"], True, ""

    # Si no hay USDT/USD, ofrecer otras opciones disponibles
    other_quotes = sorted({m.get("quote", "") for m in candidates})
    suggest = ", ".join(f"`{base_upper}/{q}`" for q in other_quotes if q)
    return None, False, (
        f"No hay {base_upper}/USDT ni {base_upper}/USD en **{ex.id}**. "
        f"Disponibles: {suggest or 'sin alternativas'}."
    )

def setup(bot):
    @bot.tree.command(name="setcoin", description="Configura el símbolo y exchange para ESTE canal (autodetecta QUOTE si falta).")
    @app_commands.describe(
        symbol="Ej: WIF/USDT o solo WIF (autodetecta QUOTE con preferencia USDT, luego USD)",
        exchange="Ej: kraken, binance, bybit, kucoin (por defecto: kraken)"
    )
    async def setcoin(interaction: Interaction, symbol: str, exchange: str = "kraken"):
        raw_sym = (symbol or "").strip()
        exn = (exchange or "").strip().lower()

        # Validar/crear exchange
        try:
            ex = getattr(ccxt, exn)()
            ex.load_markets()
        except Exception:
            return await interaction.response.send_message(
                f"⚠️ Exchange **{exn}** inválido o inaccesible. Prueba `binance`, `kraken`, `kucoin`.",
                ephemeral=True
            )

        # Caso 1: el usuario ya pone BASE/QUOTE
        if "/" in raw_sym:
            sym = raw_sym.upper()
            if sym not in ex.markets:
                return await interaction.response.send_message(
                    f"⚠️ **{exn}** no tiene **{sym}**.\n"
                    "Ejemplos: `/setcoin WIF/USD kraken`, `/setcoin WIF/USDT binance`, `/setcoin BONK/USDT kucoin`.",
                    ephemeral=True
                )
            # Comprobación rápida (403/CloudFront, etc.)
            try:
                ex.fetch_ticker(sym)
            except Exception as e:
                if _is_geoblocked(e):
                    return await interaction.response.send_message(
                        f"⚠️ Posible bloqueo regional en **{exn}** (403/CloudFront). "
                        "Usa `binance`, `kraken` o `kucoin`, o ejecuta el bot desde otra región.",
                        ephemeral=True
                    )
                return await interaction.response.send_message(
                    "⚠️ No pude consultar el ticker. Prueba nuevamente o cambia de exchange.",
                    ephemeral=True
                )
            # Guardar
            db = load_db()
            cfg = set_cfg(db, interaction.guild_id, interaction.channel_id, {"symbol": sym, "exchange": exn})
            return await interaction.response.send_message(
                "✅ Configuración actualizada para este canal:\n"
                f"**Símbolo:** `{cfg['symbol']}`\n"
                f"**Exchange:** `{cfg['exchange']}`\n"
                f"Timeframes: {', '.join(cfg['timeframes'])}"
            )

        # Caso 2: el usuario solo pone BASE (auto-elección de QUOTE)
        base = raw_sym.upper()
        chosen, was_auto, hint = _auto_pick_symbol(ex, base)
        if not chosen:
            return await interaction.response.send_message(f"⚠️ {hint}", ephemeral=True)

        # Comprobar acceso al ticker (403/CloudFront, etc.)
        try:
            ex.fetch_ticker(chosen)
        except Exception as e:
            if _is_geoblocked(e):
                return await interaction.response.send_message(
                    f"⚠️ Posible bloqueo regional en **{exn}** (403/CloudFront). "
                    "Sugerencia: usa `binance`, `kraken` o `kucoin`, o corre el bot desde otra región.",
                    ephemeral=True
                )
            return await interaction.response.send_message(
                f"⚠️ No pude consultar `{chosen}` en **{exn}**. Prueba otro exchange.",
                ephemeral=True
            )

        # Guardar config con el símbolo autodetectado
        db = load_db()
        cfg = set_cfg(db, interaction.guild_id, interaction.channel_id, {"symbol": chosen, "exchange": exn})
        nota = " (autodetectado por preferencia USDT→USD)" if was_auto else ""
        await interaction.response.send_message(
            "✅ Configuración actualizada para este canal:\n"
            f"**Símbolo:** `{cfg['symbol']}`{nota}\n"
            f"**Exchange:** `{cfg['exchange']}`\n"
            f"Timeframes: {', '.join(cfg['timeframes'])}"
        )
