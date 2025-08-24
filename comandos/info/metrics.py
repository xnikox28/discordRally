# comandos/info/metrics.py
from __future__ import annotations
import math
import pandas as pd
from comandos.grafica.render import fetch_ohlcv_df

def compute_volatility_24h(exchange: str, symbol: str) -> tuple[float | None, float | None]:
    """
    Devuelve (sigma_pct, range_pct) en 24H:
      - sigma_pct: desviación estándar (%) de los retornos de 1h de las últimas 24h
      - range_pct: (max_high - min_low) / mid * 100 en 24h
    """
    try:
        df1h = fetch_ohlcv_df(exchange, symbol, "1h", limit=28)  # un poco más que 24
        if len(df1h) < 25:
            return (None, None)

        closes = df1h["close"].astype(float).iloc[-25:]  # 25 puntos ~ 24 cambios
        returns = closes.pct_change().dropna()
        if returns.empty:
            sigma_pct = None
        else:
            sigma_pct = float(returns.std() * 100.0)

        last_24h = df1h.iloc[-24:]
        max_h = float(last_24h["high"].max())
        min_l = float(last_24h["low"].min())
        mid = (max_h + min_l) / 2.0 if (max_h and min_l) else None
        range_pct = float((max_h - min_l) / mid * 100.0) if (mid and mid > 0) else None

        return (sigma_pct, range_pct)
    except Exception:
        return (None, None)

def refine_params_by_vol(base_zz: float, base_tol: float, sigma_pct: float | None, range_pct: float | None) -> tuple[float, float, str]:
    """
    Ajusta zigzag/tolerance según volatilidad:
      - Alta vol (σ≥8% o rango≥12%): +0.010 en zigzag, +0.002 en tolerance
      - Baja vol (σ≤3% y rango≤5%):  -0.005 en zigzag, -0.001 en tolerance
      - Normal: sin cambios
    Limita a [0.02..0.10] zigzag y [0.001..0.012] tolerance.
    """
    label = "normal"
    zz, tol = base_zz, base_tol
    if (sigma_pct is not None and sigma_pct >= 8.0) or (range_pct is not None and range_pct >= 12.0):
        zz += 0.010; tol += 0.002; label = "alta"
    elif (sigma_pct is not None and sigma_pct <= 3.0) and (range_pct is not None and range_pct <= 5.0):
        zz -= 0.005; tol -= 0.001; label = "baja"

    # clamps
    zz = max(0.020, min(0.100, zz))
    tol = max(0.001, min(0.012, tol))
    return (round(zz, 3), round(tol, 3), label)
