# comandos/panel/data_adapter.py
from __future__ import annotations
from typing import Any, Iterable, List, Optional, Tuple

# Intentos de proveedores ya existentes en tu proyecto (NO impone dependencias nuevas)
try:
    from comandos.grafica.render import get_ohlcv as _get_ohlcv_render  # type: ignore
except Exception:
    _get_ohlcv_render = None  # type: ignore
try:
    from comandos.grafica.data import get_ohlcv as _get_ohlcv_data  # type: ignore
except Exception:
    _get_ohlcv_data = None  # type: ignore

def _coerce_closes(raw: Iterable[Any]) -> List[float]:
    closes: List[float] = []
    for it in (raw or []):
        if it is None:
            continue
        if isinstance(it, dict):
            for k in ("close", "c", "Close", "C", "closing_price"):
                if k in it:
                    try:
                        closes.append(float(it[k]))
                        break
                    except Exception:
                        pass
        elif isinstance(it, (list, tuple)):
            # [ts, o, h, l, c, v] (índice 4) o [o,h,l,c,...] (índice 3)
            try:
                if len(it) >= 5:
                    closes.append(float(it[4]))
                elif len(it) >= 4:
                    closes.append(float(it[3]))
            except Exception:
                pass
        else:
            try:
                closes.append(float(it))
            except Exception:
                pass
    return closes

def _try_ohlcv(fn, exchange: str, symbol: str, timeframe: str, limit: int):
    # Prueba tanto firma con kwargs como posicional
    for use_kwargs in (True, False):
        try:
            if use_kwargs:
                return fn(exchange=exchange, symbol=symbol, timeframe=timeframe, limit=limit)  # type: ignore
            else:
                return fn(exchange, symbol, timeframe, limit)  # type: ignore
        except Exception:
            continue
    return None

def _get_closes(exchange: str, symbol: str, timeframe: str, limit: int) -> Optional[List[float]]:
    funcs = [fn for fn in (_get_ohlcv_render, _get_ohlcv_data) if fn]
    if not funcs:
        return None
    # Intenta con timeframe tal cual, mayúsculas y minúsculas
    tf_variants = {timeframe, timeframe.lower(), timeframe.upper(), timeframe.capitalize()}
    ex_variants = {exchange, str(exchange).lower(), str(exchange).upper()}
    for fn in funcs:
        for tf in tf_variants:
            for ex in ex_variants:
                raw = _try_ohlcv(fn, ex, symbol, tf, limit)
                closes = _coerce_closes(raw)
                if closes:
                    return closes
    return None

def get_daily_closes_8(exchange: str, symbol: str) -> Optional[List[float]]:
    """
    Devuelve 8 cierres diarios (suficientes para 7 retornos).
    Estrategia:
      1) 1d con limit=9
      2) 4h con limit=48 (6 velas/día) -> toma cierre cada 6
      3) 1h con limit=192 (24 velas/día) -> toma cierre cada 24
    """
    # 1) 1d directo
    xs = _get_closes(exchange, symbol, "1d", 9)
    if xs and len(xs) >= 8:
        return xs[-8:]

    # 2) 4h -> 6 por día
    xs = _get_closes(exchange, symbol, "4h", 48)
    if xs and len(xs) >= 48:
        days: List[float] = []
        for i in range(6, len(xs)+1, 6):
            days.append(xs[i-1])
            if len(days) >= 8:
                break
        if len(days) >= 8:
            return days[-8:]

    # 3) 1h -> 24 por día
    xs = _get_closes(exchange, symbol, "1h", 192)
    if xs and len(xs) >= 192:
        days = []
        for i in range(24, len(xs)+1, 24):
            days.append(xs[i-1])
            if len(days) >= 8:
                break
        if len(days) >= 8:
            return days[-8:]

    return None

# ---- Diagnóstico rápido ----
def debug_probe(exchange: str, symbol: str) -> dict:
    """Devuelve un pequeño informe sobre qué rutas devolvieron datos y cuántos elementos."""
    report = {}
    for tf, lim in (("1d",9), ("4h",48), ("1h",192)):
        xs = _get_closes(exchange, symbol, tf, lim)
        report[tf] = {
            "count": len(xs) if xs else 0,
            "first_last": (xs[0], xs[-1]) if xs and len(xs) >= 2 else None
        }
    return report
