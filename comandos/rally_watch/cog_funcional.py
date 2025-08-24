import asyncio
import discord
from discord.ext import commands
from .storage import load_state, save_state
from .detect import detect_rally_aggressive, TIMEFRAMES
from .data_provider import get_ohlcv

try:
    from .alerts_store import seen
except Exception:
    import json
    from pathlib import Path as _P
    _ALERTS_FILE = _P(__file__).with_name("rally_watch_alerts.json")
    def seen(key: str, bar_ts: str) -> bool:
        try:
            data = json.loads(_ALERTS_FILE.read_text(encoding="utf-8")) if _ALERTS_FILE.exists() else {}
        except Exception:
            data = {}
        last = data.get(key)
        if last == bar_ts:
            return True
        data[key] = bar_ts
        try:
            _ALERTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass
        return False

from data_store import load_db, get_cfg

def _inject_into_command_meta():
    try:
        from comandos import comandos as comandos_mod
        meta = getattr(comandos_mod, "COMMAND_META", None)
        if isinstance(meta, dict) and "rallywatch" not in meta:
            meta["rallywatch"] = {
                "section": "Monitoreo",
                "desc": "Control de Rally Watch (activar/desactivar 15m,30m,1h,4h,1d).",
                "order": 40,
            }
    except Exception:
        pass

def _coinbase_symbol_from_channel(cfg_symbol: str) -> str:
    s = (cfg_symbol or "").upper().strip()
    if not s:
        return s
    return s.replace("/", "-")

def _embed_ignition(sym: str, tf: str, sig) -> discord.Embed:
    s = sig["state"]; lv = sig["levels"]
    e = discord.Embed(title=f"🔥 IGNITION {sym} {tf.upper()}", color=0x00ff7f)
    e.add_field(name="Estado", value=f"RSI5 **{s['rsi5']:.1f}** | EMA9 **{s['ema9']:.8f}** > EMA21 **{s['ema21']:.8f}**", inline=False)
    e.add_field(name="Entradas", value=f"EMA9: `{lv['entry_EMA9']:.8f}` | 38.2%: `{lv['entry_38.2']:.8f}`", inline=False)
    e.add_field(name="Riesgo/TP", value=f"Stop: `{lv['stop']:.8f}` | TP1: `{lv['tp1_1R']:.8f}` | TP2: `{lv['tp2_1.272']:.8f}`", inline=False)
    e.set_footer(text="Rally Watch")
    return e

def _embed_kill(sym: str, tf: str) -> discord.Embed:
    e = discord.Embed(title=f"⚠️ Killswitch {sym} {tf.upper()}", description="Posible corrección en curso.", color=0xffa500)
    e.set_footer(text="Rally Watch")
    return e

class RallyWatchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Activar TODAS (15m,30m,1h,4h,1d)", style=discord.ButtonStyle.success, custom_id="rallywatch_activate_all")
    async def activate_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        symbol = _coinbase_symbol_from_channel(cfg.get("symbol", "")) or "BONK-USD"
        st = load_state()
        st["enabled"] = True
        st["channel_id"] = interaction.channel.id
        st["symbols"] = [symbol]
        save_state(st)
        await interaction.response.send_message(f"✅ Rally Watch ACTIVADO en este canal para 15m,30m,1h,4h,1d.\nSímbolo: **{symbol}**", ephemeral=True)

    @discord.ui.button(label="Desactivar TODAS", style=discord.ButtonStyle.danger, custom_id="rallywatch_deactivate_all")
    async def deactivate_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        st = load_state()
        st["enabled"] = False
        save_state(st)
        await interaction.response.send_message("🛑 Rally Watch DESACTIVADO.", ephemeral=True)

    @discord.ui.button(label="SCAN NOW", style=discord.ButtonStyle.primary, custom_id="rallywatch_scan_now")
    async def scan_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        symbol = _coinbase_symbol_from_channel(cfg.get("symbol", "")) or "BONK-USD"
        st = load_state()
        tfs = st.get("timeframes", TIMEFRAMES)
        mult = float(st.get("keltner_mult", 1.5))
        source = st.get("data_source", "auto")
        embeds, lines = [], []
        for tf in tfs:
            try:
                df = get_ohlcv(symbol, tf, limit=600, source=source)
                if df is None or df.empty:
                    lines.append(f"• {tf.upper()}: sin datos")
                    continue
                sig = detect_rally_aggressive(df, keltner_mult=mult)
                if sig["ignition"]:
                    embeds.append(_embed_ignition(symbol, tf, sig))
                    lines.append(f"• {tf.upper()}: 🔥 IGNITION")
                elif sig["killswitch_exit"]:
                    embeds.append(_embed_kill(symbol, tf))
                    lines.append(f"• {tf.upper()}: ⚠️ Killswitch")
                else:
                    lines.append(f"• {tf.upper()}: — sin señal")
            except Exception as e:
                lines.append(f"• {tf.upper()}: error datos/detección: {e}")
        content = f"🔎 **Scan manual** {symbol}:\n" + "\n".join(lines)
        await interaction.response.send_message(content, embeds=embeds if embeds else None, ephemeral=False)

class RallyWatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bg_task = self.bot.loop.create_task(self.worker())
        _inject_into_command_meta()

    @commands.Cog.listener()
    async def on_ready(self):
        _inject_into_command_meta()

    async def worker(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            st = load_state()
            sleep_s = int(st.get("poll_seconds", 60))
            if st.get("enabled") and st.get("channel_id"):
                channel = self.bot.get_channel(st["channel_id"])
                if channel is not None:
                    db = load_db()
                    cfg = get_cfg(db, channel.guild.id, channel.id)
                    channel_symbol = _coinbase_symbol_from_channel(cfg.get("symbol", "")) or "BONK-USD"
                    symbols = [channel_symbol]
                    tfs = st.get("timeframes", TIMEFRAMES)
                    mult = float(st.get("keltner_mult", 1.5))
                    source = st.get("data_source", "auto")
                    for sym in symbols:
                        for tf in tfs:
                            try:
                                df = get_ohlcv(sym, tf, limit=600, source=source)
                                if df is None or df.empty:
                                    await channel.send(f"❗{sym} {tf}: sin datos")
                                    continue
                                sig = detect_rally_aggressive(df, keltner_mult=mult)
                                bar_ts = sig.get("bar_ts", "")
                                key_base = f"{channel.id}:{sym}:{tf}"
                                if sig["ignition"] and not seen(key_base+":IGN", bar_ts):
                                    await channel.send(embed=_embed_ignition(sym, tf, sig))
                                elif sig["killswitch_exit"] and not seen(key_base+":KILL", bar_ts):
                                    await channel.send(embed=_embed_kill(sym, tf))
                            except Exception as e:
                                try:
                                    await channel.send(f"❗{sym} {tf}: error: {e}")
                                except Exception:
                                    pass
            await asyncio.sleep(sleep_s if sleep_s>=15 else 15)

async def open_rallywatch_panel(interaction: discord.Interaction):
    view = RallyWatchView()
    await interaction.response.send_message("Control de **Rally Watch**:", view=view, ephemeral=False)
