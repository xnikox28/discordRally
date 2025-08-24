import json, os
from pathlib import Path
from typing import Dict, Any

DB_PATH = Path("state.json")

DEFAULTS = {
    "symbol": "WIF/USDT",
    "exchange": "kraken",
    "timeframes": ["4h", "1d", "1w"],
    "rally_score_needed": 3,
    "cooloff_minutes": 60,
    "rsi_rally_min": 55.0,
    "rsi_exit_overbought": 70.0,
    "vol_spike_mult": 1.5,
    "enabled": False
}

def load_db() -> Dict[str, Any]:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {}

def save_db(db: Dict[str, Any]):
    DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")

def channel_key(guild_id: int, channel_id: int) -> str:
    return f"{guild_id}:{channel_id}"

def get_cfg(db, guild_id: int, channel_id: int) -> Dict[str, Any]:
    key = channel_key(guild_id, channel_id)
    cfg = db.get(key, {}).copy()
    if not cfg:
        cfg = DEFAULTS.copy()
        db[key] = cfg
        save_db(db)
    return cfg

def set_cfg(db, guild_id: int, channel_id: int, updates: Dict[str, Any]):
    key = channel_key(guild_id, channel_id)
    cfg = db.get(key, DEFAULTS.copy())
    cfg.update(updates)
    db[key] = cfg
    save_db(db)
    return cfg

# --------------------------------------------------------------------
# Compat/Helpers (si algo externo lo llama, seguirán funcionando)
# --------------------------------------------------------------------

# Alias legacy: ahora guarda SIEMPRE en state.json
def save_cfg(db: Dict[str, Any]):
    """Compatibilidad: guarda usando state.json."""
    save_db(db)

def set_channel_param(db: Dict[str, Any], guild_id: int, channel_id: int, key: str, value):
    """
    Setter genérico que escribe en el MISMO esquema que get_cfg/set_cfg:
    clave plana 'guild:channel' dentro de state.json.
    """
    ch_key = channel_key(guild_id, channel_id)
    cfg = db.get(ch_key, DEFAULTS.copy())
    cfg[key] = value
    db[ch_key] = cfg
    save_db(db)
