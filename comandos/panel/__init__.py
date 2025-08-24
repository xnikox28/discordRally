# comandos/panel/__init__.py
from __future__ import annotations
import io
import discord
from discord import app_commands, Interaction, Embed, File
from datetime import datetime, timezone
from data_store import load_db, get_cfg, set_channel_param
from .panel import render_panel_image
from .view import PanelView

def setup(bot):
    @bot.tree.command(name="panel", description="Muestra el panel visual del canal (imagen con bloques).")
    async def panel(interaction: Interaction):
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)
        theme = cfg.get("panel_theme", "dark")  # 'dark' | 'light'
        borders = bool(cfg.get("panel_borders", True))

        # ✅ Anti-10062: defer solo si no se hizo y captura NotFound
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.NotFound:
            # Token expirado o interacción desconocida; salimos sin romper
            return
        except Exception:
            # No bloquear si el defer falla por otra causa
            pass

        try:
            img_bytes = render_panel_image(interaction.guild_id, interaction.channel_id, theme=theme, borders=borders)
            filename = f"panel_{interaction.channel_id}_{theme}_{'b' if borders else 'nb'}.png"
            file = File(io.BytesIO(img_bytes), filename=filename)

            emb = Embed(
                title="📊 Panel",
                description=f"Tema: **{theme.capitalize()}** • Bordes: **{'On' if borders else 'Off'}**",
                color=discord.Color.dark_embed() if theme == "dark" else discord.Color.light_grey(),
                timestamp=datetime.now(timezone.utc),
            )
            emb.set_image(url=f"attachment://{filename}")
            view = PanelView(theme=theme, borders=borders)

            await interaction.followup.send(embed=emb, file=file, view=view)
        except Exception as e:
            # Fallback silencioso y seguro
            try:
                await interaction.followup.send(f"⚠️ No pude renderizar el panel: `{e}`", ephemeral=True)
            except Exception:
                pass
