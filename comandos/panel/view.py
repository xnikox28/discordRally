# comandos/panel/view.py
from __future__ import annotations
import io
import discord
from discord.ui import View
from discord import Interaction, File
from data_store import load_db, get_cfg, set_channel_param
from .panel import render_panel_image

async def _ack(interaction: Interaction, *, ephemeral: bool = False) -> bool:
    """Defer seguro para evitar Unknown interaction (10062)."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
        return True
    except discord.NotFound:
        # Token expiró o botón viejo
        return False
    except Exception:
        # No bloquear por otras causas
        return True

async def _safe_edit_or_send(interaction: Interaction, *, embed: discord.Embed, file: File | None, view: discord.ui.View):
    """Edita el mensaje original; si no se puede, envía uno nuevo sin romper."""
    try:
        await interaction.followup.edit_message(
            message_id=interaction.message.id,  # type: ignore
            embed=embed,
            attachments=([file] if file else []),
            view=view
        )
    except discord.NotFound:
        # Mensaje original ya no está disponible -> enviar uno nuevo
        await interaction.followup.send(embed=embed, file=file, view=view)
    except Exception:
        # Evitar spam si nada funciona
        pass

class PanelView(View):
    def __init__(self, theme: str, borders: bool):
        super().__init__(timeout=900)
        self.theme = theme
        self.borders = borders

        # 1) Refresh button (verde) - primero a la izquierda
        self.btn_refresh = discord.ui.Button(
            label="🔄 Actualizar",
            style=discord.ButtonStyle.success
        )
        self.btn_refresh.callback = self._on_refresh
        self.add_item(self.btn_refresh)

        # 2) Theme toggle dinámico
        theme_label = "☀️ LightMode" if theme == "dark" else "🌙 DarkMode"
        theme_style = discord.ButtonStyle.secondary if theme == "dark" else discord.ButtonStyle.primary
        self.btn_theme = discord.ui.Button(label=theme_label, style=theme_style)
        self.btn_theme.callback = self._on_toggle_theme
        self.add_item(self.btn_theme)

        # 3) Borders toggle dinámico
        borders_label = "🖼️ Quitar bordes" if borders else "🖼️ Poner bordes"
        borders_style = discord.ButtonStyle.danger if borders else discord.ButtonStyle.success
        self.btn_borders = discord.ui.Button(label=borders_label, style=borders_style)
        self.btn_borders.callback = self._on_toggle_borders
        self.add_item(self.btn_borders)

    async def _update_message(self, interaction: Interaction, *, theme: str, borders: bool):
        # Render nuevo
        img_bytes = render_panel_image(interaction.guild_id, interaction.channel_id, theme=theme, borders=borders)  # type: ignore
        filename = f"panel_{interaction.channel_id}_{theme}_{'b' if borders else 'nb'}.png"
        file = File(io.BytesIO(img_bytes), filename=filename)

        # Actualizar embed
        emb = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed(title="📊 Panel")
        emb.description = f"Tema: **{theme.capitalize()}** • Bordes: **{'On' if borders else 'Off'}**"
        emb.set_image(url=f"attachment://{filename}")
        emb.color = discord.Color.dark_embed() if theme == "dark" else discord.Color.light_grey()

        # Nueva view para refrescar labels/estilos
        new_view = PanelView(theme=theme, borders=borders)

        # Edita o envía nuevo si el original ya no existe
        await _safe_edit_or_send(interaction, embed=emb, file=file, view=new_view)

    async def _on_refresh(self, interaction: Interaction):
        if not await _ack(interaction):
            return
        # Leer último estado por si otro user cambió algo
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)  # type: ignore
        theme = cfg.get("panel_theme", self.theme)
        borders = bool(cfg.get("panel_borders", self.borders))
        await self._update_message(interaction, theme=theme, borders=borders)

    async def _on_toggle_theme(self, interaction: Interaction):
        if not await _ack(interaction):
            return
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)  # type: ignore
        current = cfg.get("panel_theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        set_channel_param(db, interaction.guild_id, interaction.channel_id, "panel_theme", new_theme)  # type: ignore
        await self._update_message(interaction, theme=new_theme, borders=self.borders)

    async def _on_toggle_borders(self, interaction: Interaction):
        if not await _ack(interaction):
            return
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)  # type: ignore
        current = bool(cfg.get("panel_borders", True))
        new_borders = not current
        set_channel_param(db, interaction.guild_id, interaction.channel_id, "panel_borders", new_borders)  # type: ignore
        await self._update_message(interaction, theme=self.theme, borders=new_borders)

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: Interaction) -> None:
        # Captura de errores en callbacks; evita romper la View
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("⚠️ La interacción expiró o falló. Intenta de nuevo.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ La interacción expiró o falló. Intenta de nuevo.", ephemeral=True)
        except Exception:
            pass
