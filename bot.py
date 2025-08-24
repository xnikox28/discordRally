import os
import discord
from discord.ext import commands
from command_ids import set_guild_command_id
from dotenv import load_dotenv
from comandos import setup_commands
import inspect  # <-- para detectar si copy_global_to es coroutine o no

load_dotenv()
TOKEN = os.getenv('TOKEN') or os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

async def _safe_copy_global_to(tree: discord.app_commands.CommandTree, guild: discord.Guild):
    """
    Llama a tree.copy_global_to(guild=...) de manera segura:
    - Si es coroutine en tu versión, hacemos await.
    - Si es función normal (devuelve None), la llamamos sin await.
    - Si no existe, no hacemos nada.
    """
    func = getattr(tree, "copy_global_to", None)
    if not func:
        print(f"⚠️ Este discord.py no expone copy_global_to; se omite en {guild.name} ({guild.id})")
        return
    try:
        if inspect.iscoroutinefunction(func):
            await func(guild=guild)
        else:
            func(guild=guild)
        print(f"🛈 Copiados comandos globales a guild {guild.name} ({guild.id})")
    except Exception as e:
        print(f"⚠️ copy_global_to falló en {guild.name} ({guild.id}): {e}")

@bot.event
async def on_ready():
    import discord

    if getattr(bot, "_ready_once", False):
        return
    bot._ready_once = True


    # 🔹 Limpia registros previos (evita obsoletos/duplicados)
    bot.tree.clear_commands(guild=None)
    for g in bot.guilds:
        bot.tree.clear_commands(guild=g)

    # 🔹 Vuelve a registrar comandos de /comandos
    setup_commands(bot)

    # 🔹 Copiar globales a cada guild (versión-seguro)
    for g in bot.guilds:
        await _safe_copy_global_to(bot.tree, g)

    # 🔹 Sync inmediato por servidor + guardado de IDs para el embed cliqueable
    for g in bot.guilds:
        synced = await bot.tree.sync(guild=g)
        print(f"🔄 Sincronizados {len(synced)} comandos en guild {g.name} ({g.id})")
        for cmd in synced:
            # ⤵️ Fallback seguro: algunas versiones devuelven AppCommand sin 'qualified_name'
            qname = getattr(cmd, "qualified_name", cmd.name)
            cid = getattr(cmd, "id", None)

            # ✅ Mantengo TU print original (nombres de comandos sincronizados)
            print(f"  • {cmd.name} → {cid}")

            # 📝 Guardar ID por guild+qualified_name para que /comandos pueda mencionarlos como </cmd:ID>
            if cid:
                set_guild_command_id(g.id, qname, cid)

    # 🔹 (Opcional) sync global — puede tardar hasta ~1h en propagarse
    # await bot.tree.sync()

    await bot.change_presence(activity=discord.Game(name="Escaneando señales…"))
    print(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})") # type: ignore

@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        # mismo manejo seguro aquí
        await _safe_copy_global_to(bot.tree, guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"🆕 Guild nuevo: {guild.name} ({guild.id}) — {len(synced)} comandos copiados/sincronizados")
        for cmd in synced:
            qname = getattr(cmd, "qualified_name", cmd.name)
            cid = getattr(cmd, "id", None)
            print(f"  • {cmd.name} → {cid}")
            if cid:
                set_guild_command_id(guild.id, qname, cid)
    except Exception as e:
        print(f"❌ Error al preparar comandos en guild nuevo {guild.name} ({guild.id}): {e}")


bot.run(TOKEN) # pyright: ignore[reportArgumentType]
