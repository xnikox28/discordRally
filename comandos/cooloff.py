from discord import app_commands, Interaction
from data_store import load_db, set_cfg

def setup(bot):
    @bot.tree.command(name="cooloff", description="Define el cool-off (minutos entre alertas) para ESTE canal.")
    @app_commands.describe(minutes="Ej: 60")
    async def cooloff(interaction: Interaction, minutes: int):
        db = load_db()
        cfg = set_cfg(db, interaction.guild_id, interaction.channel_id, {"cooloff_minutes": minutes})
        await interaction.response.send_message(f"✅ cooloff = **{cfg['cooloff_minutes']} min**")
