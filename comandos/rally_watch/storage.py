
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Iterator, Tuple

FILE = Path(__file__).with_name("rally_watch_state.json")

DEFAULT_TFS = ["15m","30m","1h","4h","1d"]

def load_state() -> Dict:
    if FILE.exists():
        try:
            return json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_state(data: Dict) -> None:
    FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _default_cfg() -> Dict:
    return {
        "enabled": False,
        "symbols": [],
        "timeframes": DEFAULT_TFS,
        "poll_seconds": 60,
        "keltner_mult": 1.5,
        "data_source": "auto",
    }

def _migrate_if_needed(data: Dict) -> Dict:
    # Soporta estado antiguo con 'enabled' y 'channel_id' únicos
    if "channels" not in data:
        channels = {}
        ch = data.get("channel_id")
        if ch is not None:
            channels[str(ch)] = {
                "enabled": bool(data.get("enabled", False)),
                "symbols": data.get("symbols", []),
                "timeframes": data.get("timeframes", DEFAULT_TFS),
                "poll_seconds": data.get("poll_seconds", 60),
                "keltner_mult": data.get("keltner_mult", 1.5),
                "data_source": data.get("data_source", "auto"),
            }
        data = {"channels": channels}
        save_state(data)
    return data

def get_channel_cfg(channel_id: int) -> Dict:
    data = _migrate_if_needed(load_state())
    chs = data.setdefault("channels", {})
    return chs.get(str(channel_id), _default_cfg())

def set_channel_cfg(channel_id: int, updates: Dict) -> None:
    data = _migrate_if_needed(load_state())
    chs = data.setdefault("channels", {})
    cur = chs.get(str(channel_id), _default_cfg())
    cur.update(updates or {})
    chs[str(channel_id)] = cur
    save_state(data)

def disable_channel(channel_id: int) -> None:
    set_channel_cfg(channel_id, {"enabled": False})

def iter_channels() -> Iterator[Tuple[int, Dict]]:
    data = _migrate_if_needed(load_state())
    for cid, cfg in data.get("channels", {}).items():
        try:
            yield int(cid), cfg
        except Exception:
            continue
