from discord import app_commands, Interaction
from data_store import load_db, set_cfg

def setup(bot):
    @bot.tree.command(name="setscore", description="Define el score mínimo de rally para ESTE canal.")
    @app_commands.describe(value="Entero (3 recomendado)")
    async def setscore(interaction: Interaction, value: int):
        db = load_db()
        cfg = set_cfg(db, interaction.guild_id, interaction.channel_id, {"rally_score_needed": value})
        await interaction.response.send_message(f"✅ score mínimo para rally = **{cfg['rally_score_needed']}**")
