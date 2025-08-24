# comandos/rally_watch/detect.py
import pandas as pd
from .indicators import ema, atr, rsi_fast, keltner, slope, last_swing_low

TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"]


def detect_rally_aggressive(df: pd.DataFrame, keltner_mult=1.5):
    df = df.copy().reset_index(drop=True)
    req_cols = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = req_cols - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en DF: {missing}")
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["rsi5"] = rsi_fast(df["close"], 5)
    df["ema9_slope"] = slope(df["ema9"], 5)
    df["ema21_slope"] = slope(df["ema21"], 5)
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    mid, up, lo = keltner(df, 20, 14, keltner_mult)
    df["kel_mid"], df["kel_up"], df["kel_lo"] = mid, up, lo

    last = df.iloc[-1]
    last_time = (
        pd.to_datetime(last["timestamp"])
        if "timestamp" in df.columns
        else pd.Timestamp.utcnow()
    )  # ← NUEVO
    prev5 = df.iloc[-5:]

    trend_ok = (
        (last.ema9 > last.ema21) and (last.ema9_slope > 0) and (last.ema21_slope > 0)
    )
    breakout_ok = last.close > df["high"].rolling(20).max().shift(1).iloc[-1]
    momentum_ok = last.rsi5 >= 70
    volume_ok = (
        last["volume"] >= 1.5 * float(last["vol_ma20"])
        if pd.notna(last["vol_ma20"])
        else False
    )

    ignition = bool(trend_ok and breakout_ok and momentum_ok and volume_ok)

    above_up_seq = (prev5["close"] > prev5["kel_up"]).sum() >= 3
    rsi_hook = (prev5["rsi5"].max() > 85) and (last["rsi5"] < 70)
    close_below_ema9 = last["close"] < last["ema9"]
    sw_low = last_swing_low(df)
    structure_break = last["low"] < sw_low

    exit_now = bool((above_up_seq and close_below_ema9) or rsi_hook or structure_break)

    atr14 = float(atr(df, 14).iloc[-1])
    entry_pb_ema9 = float(last["ema9"])
    recent_low = float(df["low"].iloc[-10:-1].min())
    entry_382 = float(last["close"] - 0.382 * (last["close"] - recent_low))
    stop_conserv = float(min(sw_low, entry_pb_ema9 - atr14))
    tp1 = float(entry_pb_ema9 + (entry_pb_ema9 - stop_conserv))
    tp2 = float(entry_pb_ema9 + 1.272 * (entry_pb_ema9 - stop_conserv))

    return {
        "ignition": ignition,
        "killswitch_exit": exit_now,
        "trend_ok": bool(trend_ok),
        "breakout_ok": bool(breakout_ok),
        "momentum_ok": bool(momentum_ok),
        "volume_ok": bool(volume_ok),
        "state": {
            "close": float(last["close"]),
            "ema9": float(last["ema9"]),
            "ema21": float(last["ema21"]),
            "rsi5": float(last["rsi5"]),
            "atr14": atr14,
        },
        "bar_ts": str(
            last_time.tz_localize("UTC")
            if last_time.tzinfo is None
            else last_time.tz_convert("UTC")
        ),  # ← NUEVO
        "levels": {
            "entry_EMA9": entry_pb_ema9,
            "entry_38.2": entry_382,
            "stop": stop_conserv,
            "tp1_1R": tp1,
            "tp2_1.272": tp2,
        },
    }
