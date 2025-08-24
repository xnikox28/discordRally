from discord import app_commands, Interaction, Embed
from command_ids import get_guild_command_id  # <-- NUEVO

MAX_FIELD_LEN = 1024

COMMAND_META = {
    "start":        {"section": "Monitoreo",    "desc": "Inicia el monitoreo en este canal.",                                 "order": 10},
    "stop":         {"section": "Monitoreo",    "desc": "Detiene el monitoreo en este canal.",                                "order": 20},
    "status":       {"section": "Monitoreo",    "desc": "Muestra estado y precio actual del símbolo activo.",                 "order": 30},

    "setcoin":      {"section": "Configuración","desc": "Configura símbolo y exchange (auto-QUOTE USDT→USD).",               "order": 10},
    "settimeframes":{"section": "Configuración","desc": "Define los timeframes (ej. 4h,1d,1w).",                              "order": 20},
    "setscore":     {"section": "Configuración","desc": "Cambia el score mínimo para alertas de rally.",                      "order": 30},
    "setthresholds":{"section": "Configuración","desc": "Ajusta umbrales RSI/Volumen para señales.",                          "order": 40},
    "cooloff":      {"section": "Configuración","desc": "Minutos de enfriamiento entre alertas.",                             "order": 50},

    "sync":         {"section": "Mantenimiento","desc": "Resincroniza comandos en este servidor (solo admins).",             "order": 10},
    "comandos":     {"section": "Mantenimiento","desc": "Muestra esta lista ordenada de comandos.",                           "order": 20},
    
}

SECTION_ORDER = ["Monitoreo", "Configuración", "Mantenimiento", "Otros/Utilidades"]

def setup(bot):
    @bot.tree.command(name="comandos", description="Muestra la lista de comandos del bot (clic para abrir).")
    async def comandos(interaction: Interaction):
        global_cmds = {getattr(c, "qualified_name", c.name): c for c in bot.tree.get_commands()}
        try:
            guild_cmds = {getattr(c, "qualified_name", c.name): c for c in bot.tree.get_commands(guild=interaction.guild)}
        except Exception:
            guild_cmds = {}

        merged = dict(global_cmds)
        merged.update(guild_cmds)  # preferimos versión de guild

        buckets = {sec: [] for sec in SECTION_ORDER}
        gid = interaction.guild.id if interaction.guild else None

        for qname, cmd in sorted(merged.items(), key=lambda kv: kv[0].lower()):
            name = cmd.name
            cmd_id = getattr(cmd, "id", None)

            # 🔑 Si el objeto aún no trae id, usamos el guardado tras el sync
            if not cmd_id and gid is not None:
                saved_id = get_guild_command_id(gid, qname)
                if saved_id:
                    cmd_id = saved_id

            mention = f"</{qname}:{cmd_id}>" if cmd_id else f"/{qname}"
            meta = COMMAND_META.get(name)
            if meta:
                line = f"{mention} — {meta['desc']}"
                buckets[meta["section"]].append((meta["order"], line))
            else:
                desc = (cmd.description or "Sin descripción").strip()
                line = f"{mention} — {desc}"
                buckets["Otros/Utilidades"].append((999, line))

        embed = Embed(
            title="📜 Comandos disponibles",
            description="Haz clic en un comando para abrirlo.",
            color=0x2ecc71,
        )

        for section in SECTION_ORDER:
            items = sorted(buckets[section], key=lambda t: t[0])
            if not items:
                continue
            block, page = "", 1
            for _, line in items:
                add = line + "\n"
                if len(block) + len(add) > MAX_FIELD_LEN:
                    embed.add_field(name=f"{section} · pág. {page}", value=block, inline=False)
                    block, page = add, page + 1
                else:
                    block += add
            if block:
                embed.add_field(name=(section if page == 1 else f"{section} · pág. {page}"), value=block, inline=False)

        embed.set_footer(text="Si algún comando no sale cliqueable, usa /sync y refresca Discord (Ctrl+R en Windows).")
        await interaction.response.send_message(embed=embed)
