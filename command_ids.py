# command_ids.py
from typing import Dict

# command_ids[guild_id][qualified_name] = id(int)
command_ids: Dict[int, Dict[str, int]] = {}

def set_guild_command_id(guild_id: int, qualified_name: str, cmd_id: int):
    if guild_id not in command_ids:
        command_ids[guild_id] = {}
    command_ids[guild_id][qualified_name] = cmd_id

def get_guild_command_id(guild_id: int, qualified_name: str):
    return command_ids.get(guild_id, {}).get(qualified_name)
