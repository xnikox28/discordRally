from discord import app_commands, Interaction
from data_store import load_db, set_cfg

def setup(bot):
    @bot.tree.command(name="settimeframes", description="Define los timeframes para ESTE canal (coma-separados).")
    @app_commands.describe(timeframes="Ej: 1h,4h,1d,1w")
    async def settimeframes(interaction: Interaction, timeframes: str):
        tfs = [t.strip() for t in timeframes.split(',') if t.strip()]
        db = load_db()
        cfg = set_cfg(db, interaction.guild_id, interaction.channel_id, {"timeframes": tfs})
        await interaction.response.send_message(f"✅ Timeframes del canal: {', '.join(cfg['timeframes'])}")
