# comandos/rally_watch/__init__.py
import inspect
import discord
from discord import app_commands
from .cog import RallyWatchCog


def _ensure_unique_and_add(bot: discord.Client, cmd: app_commands.Command):
    """
    Elimina un chat_input existente con el mismo nombre y añade el nuevo
    como comando GLOBAL. Así, cuando tu bot haga copy_global_to + sync
    por guild (ver bot.py), el comando ya está en el árbol.
    """
    try:
        # Quitar cualquier comando global previo con el mismo nombre
        for existing in list(bot.tree.get_commands()):
            if getattr(existing, "name", None) == cmd.name:
                try:
                    bot.tree.remove_command(
                        existing.name,
                        type=discord.AppCommandType.chat_input,
                        guild=None,
                    )
                except Exception:
                    # remove_command no existe en algunas versiones; lo resolverá el sync por guild
                    pass
        bot.tree.add_command(cmd)  # GLOBAL
    except Exception as e:
        print(f"⚠️ No se pudo registrar /{cmd.name} globalmente: {e}")


def _register_slash_if_missing(bot: discord.Client):
    """
    Si /rallywatch no está aún en el árbol, lo registramos explícitamente
    usando la MISMA vista del Cog (RallyWatchView).
    """
    names = {
        (getattr(c, "name", "") or getattr(c, "qualified_name", "")).lower(): c
        for c in bot.tree.get_commands()
    }
    if "rallywatch" in names:
        return  # ya existe

    # Import tardío para evitar ciclos
    from .cog import RallyWatchView, open_rallywatch_panel

    @app_commands.command(
        name="rallywatch",
        description="Control de Rally Watch (activar/desactivar todas).",
    )
    async def rallywatch(interaction: discord.Interaction):
        # usa la misma UI del cog, sin duplicar lógica
        await open_rallywatch_panel(interaction)

    _ensure_unique_and_add(bot, rallywatch)


def setup(bot):
    # 1) Añadir el Cog (seguro en ambas variantes)
    result = bot.add_cog(RallyWatchCog(bot))
    if inspect.isawaitable(result):
        bot.loop.create_task(result)

    # 2) Registrar /rallywatch si aún no está en el árbol (antes del sync de tu bot)
    _register_slash_if_missing(bot)
