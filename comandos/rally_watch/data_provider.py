import os
import time
from typing import Optional
import pandas as pd

# --- Prefer real exchange data via CCXT (blocking) ---
try:
    import ccxt
    _HAS_CCXT = True
except Exception:
    _HAS_CCXT = False

import requests

_EXCH_ORDER = ["binance", "bybit", "okx", "kraken", "coinbase"]
_TF_MAP = {"15m":"15m","30m":"30m","1h":"1h","4h":"4h","1d":"1d"}

# Hard timeouts (ms) to prevent blocking the event loop too long
_CCXT_TIMEOUT_MS = int(os.getenv("RALLY_CCXT_TIMEOUT_MS", "7000"))  # 7s
_REQ_TIMEOUT = float(os.getenv("RALLY_HTTP_TIMEOUT_S", "8"))        # 8s

def _to_ccxt_symbol(symbol_dash: str) -> str:
    return symbol_dash.replace("-", "/").upper()

def _resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    rule = {"15m":"15T","30m":"30T","1h":"1H","4h":"4H","1d":"1D"}[tf]
    g = df.set_index("timestamp").resample(rule, label="right", closed="right")
    out = pd.DataFrame({
        "open": g["open"].first(),
        "high": g["high"].max(),
        "low": g["low"].min(),
        "close": g["close"].last(),
        "volume": g["volume"].sum(),
    }).dropna().reset_index()
    return out[["timestamp","open","high","low","close","volume"]]

def _fetch_ccxt_one(ex, market: str, tf: str, limit: int = 600) -> Optional[pd.DataFrame]:
    tf_ccxt = _TF_MAP.get(tf, tf)
    try:
        timeframes = getattr(ex, "timeframes", None) or {}
    except Exception:
        timeframes = {}
    try:
        if timeframes and tf_ccxt not in timeframes:
            base_tf = "15m" if tf == "30m" and "15m" in timeframes else "1h"
            ohlcv = ex.fetch_ohlcv(market, timeframe=base_tf, limit=min(limit*2, 1500))
            df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return _resample(df, tf)
        else:
            ohlcv = ex.fetch_ohlcv(market, timeframe=tf_ccxt, limit=min(limit, 1500))
            df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
    except Exception:
        return None

def _get_from_ccxt(symbol: str, tf: str, limit: int) -> Optional[pd.DataFrame]:
    if not _HAS_CCXT:
        return None
    target = _to_ccxt_symbol(symbol)  # e.g., BONK/USD
    alt = target.replace("/USD", "/USDT")
    for ex_id in _EXCH_ORDER:
        ex = None
        try:
            ex_class = getattr(ccxt, ex_id, None)
            if ex_class is None:
                continue
            ex = ex_class({"enableRateLimit": True, "timeout": _CCXT_TIMEOUT_MS})
            try:
                ex.load_markets()
            except Exception:
                continue
            market = target if target in ex.markets else (alt if alt in ex.markets else None)
            if not market:
                continue
            df = _fetch_ccxt_one(ex, market, tf, limit=limit)
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
        finally:
            try:
                if ex is not None and hasattr(ex, "close"):
                    ex.close()
            except Exception:
                pass
    return None

# ---------------- CoinGecko fallback ----------------

def _normalize_days(requested_points: int, tf: str):
    per_day = {"15m":96,"30m":48,"1h":24,"4h":6,"1d":1}.get(tf,24)
    approx_days = max(1, int(requested_points / per_day))
    for v in [1,7,14,30,90,180,365]:
        if approx_days <= v:
            return v
    return "max"

def _cg_request(url: str, params: dict, retries: int = 1, timeout: float = _REQ_TIMEOUT):
    headers = {"accept":"application/json","User-Agent":"Mozilla/5.0 RallyWatch/1.0"}
    api_key = os.getenv("COINGECKO_API_KEY") or os.getenv("CG_API_KEY")
    if api_key:
        headers["x-cg-pro-api-key"] = api_key
    last_exc = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code in (401, 403):
                r.raise_for_status()
            if r.status_code == 429 and i < retries:
                time.sleep(2.0 + i)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_exc = e
            time.sleep(0.2)
            continue
    if last_exc:
        raise last_exc

def _tf_floor_rule(tf: str) -> str:
    if tf in ("15m","30m","1h"):
        return "h"
    if tf == "4h":
        return "4h"
    return "d"

def _from_coingecko(symbol_dash: str, tf: str, limit: int = 600) -> Optional[pd.DataFrame]:
    base, quote = symbol_dash.split("-")
    coin_id = base.lower()
    vs = quote.lower()
    days = _normalize_days(limit, tf)
    interval = "hourly" if (isinstance(days, int) and days <= 30) else "daily"

    ohlc_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    ohlc = _cg_request(ohlc_url, {"vs_currency": vs, "days": days})
    if not isinstance(ohlc, list) or len(ohlc) == 0:
        return None
    df = pd.DataFrame(ohlc, columns=["timestamp","open","high","low","close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    mc_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    mc = _cg_request(mc_url, {"vs_currency": vs, "days": days, "interval": interval})
    if isinstance(mc, dict) and "total_volumes" in mc:
        vol = pd.DataFrame(mc["total_volumes"], columns=["ts","volume"])
        vol["timestamp"] = pd.to_datetime(vol["ts"], unit="ms")
        floor_rule = "h" if interval == "hourly" else "d"
        vol["bucket"] = vol["timestamp"].dt.floor(floor_rule)
        vol = vol.groupby("bucket", as_index=False)["volume"].last()
        df["bucket"] = df["timestamp"].dt.floor(_tf_floor_rule(tf))
        df = df.merge(vol.rename(columns={"bucket":"bucket","volume":"volume"}), on="bucket", how="left").drop(columns=["bucket"])
        df["volume"] = df["volume"].ffill()
    else:
        df["volume"] = pd.NA

    if limit and len(df) > limit:
        df = df.tail(limit).reset_index(drop=True)
    return df[["timestamp","open","high","low","close","volume"]]

def get_ohlcv(symbol: str, tf: str, limit: int = 600, source: str = "auto") -> Optional[pd.DataFrame]:
    if source in ("auto","exchange","ccxt"):
        try:
            df = _get_from_ccxt(symbol, tf, limit)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
    try:
        return _from_coingecko(symbol, tf, limit=limit)
    except requests.HTTPError as e:  # type: ignore[name-defined]
        print(f"CoinGecko HTTP {e.response.status_code}: {e}")
        return None
    except Exception as e:
        print(f"CoinGecko provider error for {symbol} {tf}: {e}")
        return None
