from typing import Optional
from discord import app_commands, Interaction
from data_store import load_db, set_cfg

def setup(bot):
    @bot.tree.command(name="setthresholds", description="Ajusta umbrales RSI/Volumen para ESTE canal.")
    @app_commands.describe(rsi_rally_min="RSI mínimo para rally (default 55)",
                           rsi_exit_overbought="RSI salida sobrecompra (default 70)",
                           vol_spike_mult="Multiplicador volumen (default 1.5)")
    async def setthresholds(interaction: Interaction, 
                            rsi_rally_min: Optional[float]=None,
                            rsi_exit_overbought: Optional[float]=None,
                            vol_spike_mult: Optional[float]=None):
        updates = {}
        if rsi_rally_min is not None: updates["rsi_rally_min"] = rsi_rally_min
        if rsi_exit_overbought is not None: updates["rsi_exit_overbought"] = rsi_exit_overbought
        if vol_spike_mult is not None: updates["vol_spike_mult"] = vol_spike_mult
        db = load_db()
        cfg = set_cfg(db, interaction.guild_id, interaction.channel_id, updates)
        await interaction.response.send_message(
            f"✅ Umbrales: rsi_rally_min={cfg['rsi_rally_min']}, "
            f"rsi_exit_overbought={cfg['rsi_exit_overbought']}, vol_spike_mult={cfg['vol_spike_mult']}"
        )
