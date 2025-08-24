# comandos/panel/coingecko_adapter.py
from __future__ import annotations
from typing import Optional, Tuple, List
import time

# Usamos requests si está disponible (suele estar en tu venv). Si no, desactivamos el adapter.
try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

_API = "https://api.coingecko.com/api/v3"
_CACHE: dict = {}
_TTL = 60  # segundos de cache básico para evitar rate limits

def _cache_get(key: str):
    v = _CACHE.get(key)
    if not v: return None
    ts, data = v
    if time.time() - ts > _TTL:
        return None
    return data

def _cache_set(key: str, data):
    _CACHE[key] = (time.time(), data)

def _vs_from_quote(quote: Optional[str]) -> str:
    if not quote:
        return "usd"
    q = quote.strip().upper()
    if q in ("USD", "USDT", "USDC"):
        return "usd"
    # Otros casos: intentar lower directamente (cg soporta varias fiat/cripto como vs_currency? lo común es fiat)
    return q.lower()

def _search_coin_id(symbol_or_name: str) -> Optional[str]:
    if requests is None:
        return None
    q = symbol_or_name.strip()
    key = f"cg:search:{q}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        resp = requests.get(f"{_API}/search", params={"query": q}, timeout=6)
        if resp.status_code != 200:
            return None
        data = resp.json() or {}
        coins = data.get("coins") or []
        # Preferimos match exacto por symbol (case-insensitive), luego por nombre que empiece igual
        up = q.upper()
        best_id = None
        for c in coins:
            sym = (c.get("symbol") or "").upper()
            name = (c.get("name") or "")
            cid  = c.get("id")
            if not cid: 
                continue
            if sym == up:
                best_id = cid
                break
            if not best_id and name.lower().startswith(q.lower()):
                best_id = cid
        if not best_id and coins:
            best_id = coins[0].get("id")
        _cache_set(key, best_id)
        return best_id
    except Exception:
        return None

def get_daily_closes_8_cg(base_symbol: str, quote: Optional[str]) -> Tuple[Optional[List[float]], Optional[str]]:
    """
    Devuelve (closes[8], vs_currency) usando CoinGecko market_chart (interval=daily).
    base_symbol: por ej. 'WIF', 'BTC' (sin quote)
    quote: 'USD'/'USDT'/... -> mapeado a 'usd' (cg trabaja en vs_currency fiat)
    """
    if requests is None:
        return None, None
    coin_id = _search_coin_id(base_symbol)
    if not coin_id:
        return None, None
    vs = _vs_from_quote(quote)
    key = f"cg:chart:{coin_id}:{vs}:8"
    cached = _cache_get(key)
    if cached is not None:
        return cached, vs
    try:
        # days=8 trae 8 puntos de cierre diario (incluye el día actual/último disponible)
        resp = requests.get(f"{_API}/coins/{coin_id}/market_chart", params={"vs_currency": vs, "days": 8, "interval": "daily"}, timeout=6)
        if resp.status_code != 200:
            return None, None
        data = resp.json() or {}
        prices = data.get("prices") or []  # lista de [ts, price]
        closes: List[float] = []
        for p in prices:
            try:
                closes.append(float(p[1]))
            except Exception:
                continue
        if len(closes) >= 8:
            closes = closes[-8:]
            _cache_set(key, closes)
            return closes, vs
        return None, None
    except Exception:
        return None, None
