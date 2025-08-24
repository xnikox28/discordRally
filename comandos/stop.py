from discord import app_commands, Interaction
from data_store import load_db, set_cfg
import monitor

def setup(bot):
    @bot.tree.command(name="stop", description="Detiene el monitoreo en ESTE canal.")
    async def stop(interaction: Interaction):
        db = load_db()
        set_cfg(db, interaction.guild_id, interaction.channel_id, {"enabled": False})
        stopped = monitor.stop_channel(interaction.guild_id, interaction.channel_id)
        if stopped:
            await interaction.response.send_message("🛑 Monitoreo **detenido** para este canal.")
        else:
            await interaction.response.send_message("ℹ️ No había tarea activa; deshabilitado en config.")
