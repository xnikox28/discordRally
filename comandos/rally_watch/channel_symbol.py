from pathlib import Path
import json

def get_channel_symbol(project_root: Path, channel_id: int, default_symbol: str) -> str:
    """
    Lee state.json de la raíz y devuelve el símbolo activo para ese canal, si existe.
    Estructura esperada: claves tipo "<channel_id>:<user_id>" -> { "symbol": "WIF/USD", ... }
    """
    try:
        state_file = project_root / "state.json"
        if not state_file.exists():
            return default_symbol
        obj = json.loads(state_file.read_text(encoding="utf-8"))
        prefix = f"{channel_id}:"
        for k, v in obj.items():
            if k.startswith(prefix) and isinstance(v, dict) and "symbol" in v:
                sym = v.get("symbol") or default_symbol
                return sym.replace(" ", "").replace("\\", "/")
        return default_symbol
    except Exception:
        return default_symbol
