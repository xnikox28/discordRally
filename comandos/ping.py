# comandos/ping.py
from discord import app_commands, Interaction, Object

GUILD_ID = 934453561889263688  # pon aquí el ID de tu servidor de pruebas (el mismo que usaste en /sync)

def setup(bot):
    @bot.tree.command(name="ping", description="Prueba de vida (simple).")
    @app_commands.guilds(Object(id=GUILD_ID))  # ← solo para tu server, temporal
    async def ping(interaction: Interaction):
        print(">>> handler /ping ejecutado")
        await interaction.response.send_message("🏓 Pong!")

