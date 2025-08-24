# comandos/ids.py
from discord import app_commands, Interaction, Embed

def setup(bot):
    @bot.tree.command(name="ids", description="Lista comandos visibles para este servidor (debug).")
    async def ids(interaction: Interaction):
        await interaction.response.send_message("⏳ Recolectando…", ephemeral=True)
        names = [getattr(c, "qualified_name", c.name) for c in bot.tree.get_commands()]
        names.sort(key=str.lower)
        emb = Embed(title="Comandos en el árbol", description="\n".join(names) or "—")
        await interaction.followup.send(embed=emb, ephemeral=True)
