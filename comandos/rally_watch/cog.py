import os
import asyncio
import discord
from discord.ext import commands
from .storage import get_channel_cfg, set_channel_cfg, iter_channels, DEFAULT_TFS
from .detect import detect_rally_aggressive
from .data_provider import get_ohlcv
from .plotter import make_chart

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

CHART_DIR = os.path.join(os.path.dirname(__file__), "_charts")

def _inject_into_command_meta():
    try:
        from comandos import comandos as comandos_mod
        meta = getattr(comandos_mod, "COMMAND_META", None)
        if isinstance(meta, dict) and "rallywatch" not in meta:
            meta["rallywatch"] = {
                "section": "Monitoreo",
                "desc": "Control de Rally Watch (activar/desactivar 15m,30m,1h,4h,1d) + SCAN NOW.",
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
        set_channel_cfg(interaction.channel.id, {"enabled": True, "symbols": [symbol]})
        await interaction.response.send_message(
            f"✅ Rally Watch ACTIVADO en este canal para 15m,30m,1h,4h,1d.\nSímbolo: **{symbol}**",
            ephemeral=True
        )

    @discord.ui.button(label="Desactivar TODAS", style=discord.ButtonStyle.danger, custom_id="rallywatch_deactivate_all")
    async def deactivate_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        set_channel_cfg(interaction.channel.id, {"enabled": False})
        await interaction.response.send_message("🛑 Rally Watch DESACTIVADO en este canal.", ephemeral=True)

    @discord.ui.button(label="SCAN NOW", style=discord.ButtonStyle.primary, custom_id="rallywatch_scan_now")
    async def scan_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)

        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        symbol = _coinbase_symbol_from_channel(cfg.get("symbol", "")) or "BONK-USD"

        ch_cfg = get_channel_cfg(interaction.channel.id)
        tfs = ch_cfg.get("timeframes", DEFAULT_TFS)
        mult = float(ch_cfg.get("keltner_mult", 1.5))
        source = ch_cfg.get("data_source", "auto")

        embeds, files, lines = [], [], []
        for tf in tfs:
            try:
                df = await asyncio.to_thread(get_ohlcv, symbol, tf, 600, source)
                if df is None or df.empty:
                    lines.append(f"• {tf.upper()}: sin datos")
                    continue
                sig = detect_rally_aggressive(df, keltner_mult=mult)
                path = None
                if sig["ignition"] or sig["killswitch_exit"]:
                    path = await asyncio.to_thread(make_chart, df, symbol, tf, CHART_DIR)
                if sig["ignition"]:
                    e = _embed_ignition(symbol, tf, sig)
                    if path:
                        fn = os.path.basename(path); e.set_image(url=f"attachment://{fn}")
                        files.append(discord.File(path, filename=fn))
                    embeds.append(e)
                    lines.append(f"• {tf.upper()}: 🔥 IGNITION")
                elif sig["killswitch_exit"]:
                    e = _embed_kill(symbol, tf)
                    if path:
                        fn = os.path.basename(path); e.set_image(url=f"attachment://{fn}")
                        files.append(discord.File(path, filename=fn))
                    embeds.append(e)
                    lines.append(f"• {tf.upper()}: ⚠️ Killswitch")
                else:
                    lines.append(f"• {tf.upper()}: — sin señal")
            except Exception as e:
                lines.append(f"• {tf.upper()}: error datos/detección: {e}")

        content = "🔎 **Scan manual** {sym}:\n{rows}".format(sym=symbol, rows="\n".join(lines))
        if embeds:
            await interaction.followup.send(content, embeds=embeds[:10], files=files[:10])
        else:
            await interaction.followup.send(content)

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
            for channel_id, ch_cfg in iter_channels():
                if not ch_cfg.get("enabled"):
                    continue
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    continue
                try:
                    db = load_db()
                    cfg = get_cfg(db, channel.guild.id, channel.id)
                    channel_symbol = _coinbase_symbol_from_channel(cfg.get("symbol", "")) or "BONK-USD"
                    tfs = ch_cfg.get("timeframes", DEFAULT_TFS)
                    mult = float(ch_cfg.get("keltner_mult", 1.5))
                    source = ch_cfg.get("data_source", "auto")
                    for tf in tfs:
                        try:
                            df = await asyncio.to_thread(get_ohlcv, channel_symbol, tf, 600, source)
                            if df is None or df.empty:
                                await channel.send(f"❗{channel_symbol} {tf}: sin datos")
                                continue
                            sig = detect_rally_aggressive(df, keltner_mult=mult)
                            bar_ts = sig.get("bar_ts", "")
                            key_base = f"{channel.id}:{channel_symbol}:{tf}"
                            if sig["ignition"] and not seen(key_base + ":IGN", bar_ts):
                                path = await asyncio.to_thread(make_chart, df, channel_symbol, tf, CHART_DIR)
                                fn = os.path.basename(path)
                                file = discord.File(path, filename=fn)
                                emb = _embed_ignition(channel_symbol, tf, sig)
                                emb.set_image(url=f"attachment://{fn}")
                                await channel.send(embed=emb, file=file)
                            elif sig["killswitch_exit"] and not seen(key_base + ":KILL", bar_ts):
                                path = await asyncio.to_thread(make_chart, df, channel_symbol, tf, CHART_DIR)
                                fn = os.path.basename(path)
                                file = discord.File(path, filename=fn)
                                emb = _embed_kill(channel_symbol, tf)
                                emb.set_image(url=f"attachment://{fn}")
                                await channel.send(embed=emb, file=file)
                        except Exception as e:
                            try:
                                await channel.send(f"❗{channel_symbol} {tf}: error: {e}")
                            except Exception:
                                pass
                except Exception:
                    pass
            await asyncio.sleep(60 if 60 >= 15 else 15)

async def open_rallywatch_panel(interaction: discord.Interaction):
    view = RallyWatchView()
    await interaction.response.send_message("Control de **Rally Watch**:", view=view, ephemeral=False)
