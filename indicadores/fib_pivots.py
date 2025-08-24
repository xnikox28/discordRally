# indicadores/fib_pivots.py
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pandas as pd

# ========== Utilidades numéricas ==========
def _nan(x): 
    try: 
        return math.isnan(x)
    except Exception:
        return False

def _as_float(x):
    try:
        return float(x)
    except Exception:
        return None

# ========== 1) Swings (ZigZag “suave”) ==========
def find_swings_zigzag(
    df: pd.DataFrame, 
    pct: float = 0.03,         # 3% por defecto
    min_bars: int = 5,         # separación mínima de velas entre swings
) -> List[Tuple[pd.Timestamp, float, str]]:
    """
    Devuelve una lista de swings [(ts, price, kind)] con kind ∈ {'H','L'}
    usando un zigzag por umbral porcentual.
    Espera df con columnas: high, low, close (índice datetime UTC).
    """
    if df is None or len(df) < 10:
        return []

    highs = df['high'].astype(float)
    lows  = df['low'].astype(float)

    swings: List[Tuple[pd.Timestamp, float, str]] = []

    # Comenzamos asumiendo último pivot como mínimo o máximo local
    last_pivot_idx = highs.index[0]
    last_pivot_price = highs.iloc[0]
    last_pivot_kind = 'H'  # lo corregimos rápido

    # Elegimos pivot inicial
    if highs.iloc[0] - lows.iloc[0] >= 0:
        last_pivot_price = highs.iloc[0]
        last_pivot_kind = 'H'
    else:
        last_pivot_price = lows.iloc[0]
        last_pivot_kind = 'L'

    swings.append((last_pivot_idx, float(last_pivot_price), last_pivot_kind))

    for i in range(1, len(df)):
        ts = highs.index[i]
        h  = float(highs.iloc[i])
        l  = float(lows.iloc[i])

        if last_pivot_kind == 'H':
            # Buscamos mínimo relativo
            drop = (last_pivot_price - l) / last_pivot_price
            if drop >= pct and (i - df.index.get_indexer([last_pivot_idx])[0]) >= min_bars:
                # nuevo swing L
                last_pivot_idx = ts
                last_pivot_price = l
                last_pivot_kind = 'L'
                swings.append((ts, l, 'L'))
            else:
                # Actualizar pivot H si hay un high más alto
                if h > last_pivot_price:
                    swings[-1] = (ts, h, 'H')
                    last_pivot_idx = ts
                    last_pivot_price = h
        else:
            # last was L → buscamos H
            rise = (h - last_pivot_price) / last_pivot_price
            if rise >= pct and (i - df.index.get_indexer([last_pivot_idx])[0]) >= min_bars:
                last_pivot_idx = ts
                last_pivot_price = h
                last_pivot_kind = 'H'
                swings.append((ts, h, 'H'))
            else:
                if l < last_pivot_price:
                    swings[-1] = (ts, l, 'L')
                    last_pivot_idx = ts
                    last_pivot_price = l

    return swings

# ========== 2) Fibonacci “inteligente” ==========
@dataclass
class FibSet:
    direction: str            # 'up' o 'down'
    base: float               # precio base (swing)
    anchor: float             # precio ancla (swing opuesto)
    levels: Dict[str, float]  # {'0.236': price, ...}

FIB_RATIOS_DEFAULT = [
    0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618
]

def fib_from_swings(
    last_high: float, last_low: float, 
    direction_hint: Optional[str] = None,
    ratios: List[float] = FIB_RATIOS_DEFAULT
) -> FibSet:
    """
    Genera niveles fibo entre el último swing low y high.
    direction_hint:
      - 'up'   : medimos retrocesos sobre un tramo alcista (low→high)
      - 'down' : medimos retrocesos sobre un tramo bajista (high→low)
      - None   : decide por magnitud del último tramo
    """
    last_high = float(last_high); last_low = float(last_low)

    # Decidir dirección
    if direction_hint in ('up','down'):
        direction = direction_hint
    else:
        direction = 'up' if (last_high - last_low) >= abs(last_low - last_high) else 'down'

    levels: Dict[str, float] = {}
    if direction == 'up':
        base, anchor = last_low, last_high
        span = anchor - base
        for r in ratios:
            levels[f"{r:g}"] = anchor - span * r  # retrocesos desde el tope
    else:
        base, anchor = last_high, last_low
        span = base - anchor
        for r in ratios:
            levels[f"{r:g}"] = anchor + span * r

    return FibSet(direction=direction, base=base, anchor=anchor, levels=levels)

def intelligent_fib(
    df: pd.DataFrame,
    rsi_col: str = 'rsi14',
    ema_fast: str = 'ema20',
    ema_slow: str = 'ema50',
    zigzag_pct: float = 0.03,
    min_bars: int = 5
) -> Optional[FibSet]:
    """
    1) Detecta swings con zigzag (3% por defecto).
    2) Decide dirección por estructura:
       - close > ema_fast > ema_slow y rsi > 50 → 'up'
       - close < ema_fast < ema_slow y rsi < 50 → 'down'
       - si dudoso → decide por último tramo de swings.
    3) Construye niveles Fibonacci del último tramo significativo.
    """
    if df is None or len(df) < 50:
        return None
    c = df['close'].astype(float)
    rsi = df[rsi_col] if rsi_col in df.columns else None
    ef  = df[ema_fast] if ema_fast in df.columns else None
    es  = df[ema_slow] if ema_slow in df.columns else None

    swings = find_swings_zigzag(df, pct=zigzag_pct, min_bars=min_bars)
    if len(swings) < 2:
        return None

    # Últimos dos swings de tipos distintos (H y L)
    last = swings[-1]
    prev = next((s for s in reversed(swings[:-1]) if s[2] != last[2]), None)
    if prev is None:
        return None

    last_price = float(c.iloc[-1])
    dir_hint = None
    try:
        efv = float(ef.iloc[-1]) if ef is not None else None
        esv = float(es.iloc[-1]) if es is not None else None
        rsiv = float(rsi.iloc[-1]) if rsi is not None else None

        if efv and esv and rsiv is not None:
            if last_price > efv > esv and rsiv > 50:
                dir_hint = 'up'
            elif last_price < efv < esv and rsiv < 50:
                dir_hint = 'down'
    except Exception:
        pass

    # tramo base para fib: del swing opuesto al último
    if last[2] == 'H':
        last_high = last[1]; last_low = prev[1]
    else:
        last_low = last[1]; last_high = prev[1]

    return fib_from_swings(last_high=last_high, last_low=last_low, direction_hint=dir_hint)

# ========== 3) Pivots clásicos ==========
@dataclass
class PivotLevels:
    P: float
    R1: float; R2: float; R3: float
    S1: float; S2: float; S3: float

def classic_pivots_from_ohlc(h: float, l: float, c: float) -> PivotLevels:
    P = (h + l + c) / 3.0
    R1 = 2*P - l
    S1 = 2*P - h
    R2 = P + (h - l)
    S2 = P - (h - l)
    R3 = h + 2*(P - l)
    S3 = l - 2*(h - P)
    return PivotLevels(P=P, R1=R1, R2=R2, R3=R3, S1=S1, S2=S2, S3=S3)

def classic_pivots_from_df_daily(df_daily: pd.DataFrame) -> Optional[PivotLevels]:
    """
    Usa la ÚLTIMA vela COMPLETA diaria (penúltima fila si la última está en curso).
    Espera columnas: high, low, close
    """
    if df_daily is None or len(df_daily) < 2:
        return None
    # penúltima fila = día previo completo
    row = df_daily.iloc[-2]
    return classic_pivots_from_ohlc(_as_float(row.high), _as_float(row.low), _as_float(row.close))

# ========== 4) Confluencia “inteligente” (FIB + Pivots + EMAs + swings) ==========
@dataclass
class Zone:
    level: float
    kind: str            # 'R' o 'S'
    tags: List[str]      # ['FIB_0.618','PIVOT_R1','EMA200','SWING_H']
    score: float

def _proximity(a: float, b: float) -> float:
    """ distancia relativa |a-b|/a """
    try:
        return abs(a - b) / max(1e-12, abs(a))
    except Exception:
        return 1.0

def build_zones_confluence(
    df: pd.DataFrame,
    fib: Optional[FibSet],
    pivots: Optional[PivotLevels],
    ema_cols: Tuple[str, ...] = ('ema20','ema50','ema100','ema200'),
    swing_window: int = 50,
    price_tolerance: float = 0.002  # 0.2% para fusionar niveles cercanos
) -> List[Zone]:
    """
    Crea zonas por confluencia:
      - niveles FIB (0.236, 0.382, 0.5, 0.618, 0.786)
      - Pivots R1..R3 / S1..S3
      - EMAs relevantes
      - High/Low de los últimos N candles (swings locales)
    Puntúa por cercanía y # de “etiquetas” (confluencias).
    """
    if df is None or len(df) < 30:
        return []

    c = df['close'].astype(float)
    last = float(c.iloc[-1])

    # 1) Coleccionar candidatos [price, tag, kind]
    candidates: List[Tuple[float, str, str]] = []

    if fib is not None:
        for k, v in fib.levels.items():
            kv = float(v)
            # filtramos extensiones mayores a 1.272 si no quieres sobrecargar
            if k in ('0.236','0.382','0.5','0.618','0.786','1'):
                kind = 'S' if kv < last else 'R'
                candidates.append((kv, f"FIB_{k}", kind))

    if pivots is not None:
        for name in ['R1','R2','R3','S1','S2','S3']:
            kv = float(getattr(pivots, name))
            kind = 'R' if name.startswith('R') else 'S'
            candidates.append((kv, f"PIVOT_{name}", kind))

    for col in ema_cols:
        if col in df.columns:
            kv = float(df[col].iloc[-1])
            kind = 'S' if kv < last else 'R'
            candidates.append((kv, col.upper(), kind))

    # swings locales (high/low recientes)
    w = min(len(df), max(10, swing_window))
    loc_high = float(df['high'].iloc[-w:].max())
    loc_low  = float(df['low'].iloc[-w:].min())
    candidates.append((loc_high, "SWING_H", 'R'))
    candidates.append((loc_low,  "SWING_L", 'S'))

    # 2) Fusionar por proximidad (clustering lineal simple)
    groups: List[List[Tuple[float, str, str]]] = []
    candidates.sort(key=lambda x: x[0])  # sort por precio
    for price, tag, kind in candidates:
        placed = False
        for g in groups:
            piv = sum([p for p,_,_ in g]) / len(g)
            if _proximity(piv, price) <= price_tolerance:
                g.append((price, tag, kind))
                placed = True
                break
        if not placed:
            groups.append([(price, tag, kind)])

    # 3) Puntuar grupos
    zones: List[Zone] = []
    for g in groups:
        price_avg = sum([p for p,_,_ in g]) / len(g)
        tags = [t for _,t,_ in g]
        # kind dominante por mayoría
        rs = [k for _,_,k in g]
        kind = 'R' if rs.count('R') >= rs.count('S') else 'S'

        # score por #confluencias + cercanía a precio actual
        conf = len(set(tags))                      # diversidad de tags
        prox = max(0.0, 1.0 - _proximity(last, price_avg) / price_tolerance)
        score = conf * 1.0 + prox * 1.0

        zones.append(Zone(level=price_avg, kind=kind, tags=sorted(set(tags)), score=round(score, 3)))

    # ordenar: primero score alto; dentro, R por arriba / S por debajo del precio
    zones.sort(key=lambda z: (-z.score, (z.level - last)))
    return zones
