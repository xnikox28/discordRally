from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

# ========= Technicals (pro-grade) =========
def rma(series: pd.Series, period: int) -> pd.Series:
    """Wilder's RMA (TradingView's 'rma')."""
    return series.ewm(alpha=1/period, adjust=False).mean()

def rsi_wilder(close: pd.Series, period: int = 5) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = rma(gain, period)
    avg_loss = rma(loss, period)
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi.bfill().fillna(50)

# ========= Plot =========
def make_chart(df: pd.DataFrame, symbol: str, tf: str, out_dir: str | Path) -> str:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = df.copy().tail(200).reset_index(drop=True)
    data["ema9"] = data["close"].ewm(span=9, adjust=False).mean()
    data["ema21"] = data["close"].ewm(span=21, adjust=False).mean()
    data["rsi5"] = rsi_wilder(data["close"], period=5)

    x = range(len(data))
    xticks_idx = list(range(0, len(data), max(1, len(data)//6)))
    xtick_labels = [data["timestamp"].iloc[i].strftime("%m-%d %H:%M") for i in xticks_idx]

    fig = plt.figure(figsize=(9, 6), dpi=140)
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1.2], hspace=0.25)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(x, data["close"], linewidth=1.2, label="Close")
    ax1.plot(x, data["ema9"], linewidth=1.2, label="EMA9")
    ax1.plot(x, data["ema21"], linewidth=1.2, label="EMA21")
    ax1.set_title(f"{symbol} • {tf.upper()}")
    ax1.set_ylabel("Precio")
    ax1.set_xticks(xticks_idx, labels=xtick_labels, rotation=0, fontsize=8)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.2)

    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(x, data["rsi5"], linewidth=1.2, label="RSI5 (Wilder)")
    for lvl in (70, 50, 30):
        ax2.axhline(lvl, linestyle="--", linewidth=0.8)
    ax2.set_ylabel("RSI5")
    ax2.set_xticks(xticks_idx, labels=xtick_labels, rotation=0, fontsize=8)
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.2)

    fname = f"{symbol.replace('/', '-').replace(' ', '')}_{tf}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    out_path = out_dir / fname
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)
