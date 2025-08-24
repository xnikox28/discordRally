from discord import app_commands, Interaction, Object

GUILD_ID = 934453561889263688

def setup(bot):
    @bot.tree.command(name="sync", description="Resincroniza los slash commands en este servidor.")
    @app_commands.guilds(Object(id=GUILD_ID))
    async def sync(interaction: Interaction):
        try:
            # 1) Permisos
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("⛔ Solo administradores pueden usar este comando.", ephemeral=True)
                return

            # 2) Asegura respuesta < 3s (evita 'app did not respond')
            await interaction.response.defer(thinking=True, ephemeral=True)

            # 3) Sync por-guild (instantáneo en este servidor)
            await bot.tree.sync(guild=interaction.guild)

            # 4) Confirmación
            await interaction.followup.send("🔄 Comandos resincronizados en este servidor.")
        except Exception as e:
            # Log en consola
            print(f"/sync error: {e!r}")
            # Si ya hicimos defer, usamos followup; si no, respondemos normal
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Error al sincronizar: `{e}`")
            else:
                await interaction.response.send_message(f"❌ Error al sincronizar: `{e}`", ephemeral=True)
