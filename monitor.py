import asyncio
from datetime import datetime, timezone
from typing import Dict, Tuple

import ccxt
import pandas as pd

from data_store import channel_key, get_cfg, load_db
from signals import compute_indicators, exit_signals, rally_signals
from ui import make_correction_embed, make_rally_embed  # UI embeds

_bot = None
scan_tasks: Dict[str, asyncio.Task] = {}
last_alert_ts: Dict[Tuple[str, str], float] = {}


def init(bot):
    global _bot
    _bot = bot


def utc_now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_exchange(name):
    ex = getattr(ccxt, name)()
    ex.load_markets()
    return ex


def fetch_ohlcv_df(exchange, symbol, timeframe="4h", limit=300):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    df = pd.DataFrame(ohlcv, columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")


async def scan_loop(guild_id: int, channel_id: int):
    channel = _bot.get_channel(channel_id)  # type: ignore
    if channel is None:
        return
    await channel.send(f"🛰️ Monitoreo iniciado para este canal. ({utc_now_str()})")

    while True:
        try:
            db = load_db()
            cfg = get_cfg(db, guild_id, channel_id)
            if not cfg.get("enabled", False):
                await asyncio.sleep(5)
                continue

            symbol = cfg["symbol"]
            exchange_name = cfg["exchange"]
            timeframes = cfg["timeframes"]
            score_need = cfg["rally_score_needed"]
            cooloff = cfg["cooloff_minutes"] * 60
            rsi_rally_min = cfg["rsi_rally_min"]
            rsi_exit = cfg["rsi_exit_overbought"]
            vol_mult = cfg["vol_spike_mult"]

            # 🔧 parámetros aplicados desde state.json (con defaults si no existen)
            zigzag_pct = float(cfg.get("zigzag_pct", 0.03))
            price_tol = float(cfg.get("price_tolerance", 0.002))

            ex = get_exchange(exchange_name)

            for tf in timeframes:
                try:
                    df = fetch_ohlcv_df(ex, symbol, timeframe=tf)
                    df = compute_indicators(df)
                    score, why = rally_signals(
                        df, rsi_min=rsi_rally_min, vol_mult=vol_mult
                    )
                    exits = exit_signals(df, rsi_over=rsi_exit)

                    ch_key = channel_key(guild_id, channel_id)
                    key_tf = (ch_key, tf)
                    now_mono = asyncio.get_event_loop().time()
                    cooldown_ok = (now_mono - last_alert_ts.get(key_tf, 0)) > cooloff

                    # Última vela para datos de precio/RSI
                    c = df.iloc[-1]

                    if score >= score_need and cooldown_ok:
                        last_alert_ts[key_tf] = now_mono
                        emb = make_rally_embed(
                            symbol=symbol,
                            exchange=exchange_name,
                            timeframe=tf,
                            price=float(c.close) if pd.notna(c.close) else None,
                            rsi=float(c.rsi) if pd.notna(c.rsi) else None,
                            vol_mult=None,
                            score=int(score),
                        )
                        # 🦶 footer con razones + parámetros aplicados
                        footer_extra = f"zigzag={zigzag_pct:.3f} • tol={price_tol:.3f}"
                        if why:
                            emb.set_footer(text=f"{'; '.join(why)} • {footer_extra}")
                        else:
                            emb.set_footer(text=footer_extra)
                        await channel.send(embed=emb)

                    if len(exits) >= 2 and cooldown_ok:
                        last_alert_ts[key_tf] = now_mono
                        reason = " | ".join(exits) if exits else None
                        emb = make_correction_embed(
                            symbol=symbol,
                            exchange=exchange_name,
                            timeframe=tf,
                            price=float(c.close) if pd.notna(c.close) else None,
                            rsi=float(c.rsi) if pd.notna(c.rsi) else None,
                            reason=reason,
                        )
                        footer_extra = f"zigzag={zigzag_pct:.3f} • tol={price_tol:.3f}"
                        if reason:
                            emb.set_footer(text=f"{reason} • {footer_extra}")
                        else:
                            emb.set_footer(text=footer_extra)
                        await channel.send(embed=emb)

                except Exception as e:
                    await channel.send(f"⚠️ Error `{symbol}` `{tf}`: `{e}`")

            await asyncio.sleep(300)
        except Exception as e:
            try:
                await channel.send(f"⚠️ Loop error: `{e}`")
            except Exception:
                pass
            await asyncio.sleep(10)


def start_channel(guild_id: int, channel_id: int):
    ch_key = channel_key(guild_id, channel_id)
    if ch_key in scan_tasks and not scan_tasks[ch_key].done():
        return False
    task = asyncio.create_task(scan_loop(guild_id, channel_id))
    scan_tasks[ch_key] = task
    return True


def stop_channel(guild_id: int, channel_id: int):
    ch_key = channel_key(guild_id, channel_id)
    t = scan_tasks.get(ch_key)
    if t and not t.done():
        t.cancel()
        return True
    return False
