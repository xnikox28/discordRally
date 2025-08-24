
# comandos/grafica/view.py
import io, time, traceback
import discord
from discord import File, Embed, Interaction
from discord.ui import View
from datetime import datetime, timezone
from .render import fetch_ohlcv_df, render_png, get_last_price, get_change_24h_pct
from .utils import fmt_price, fmt_pct, color_pct, trend_emoji_from  # ← utilidades

class GraficaView(View):
    def __init__(self, symbol: str, exchange: str, timeframes: list[str], current_tf: str):
        super().__init__(timeout=600)
        self.symbol = symbol
        self.exchange = exchange
        seen = set()
        self.timeframes = [tf.lower() for tf in (timeframes or []) if not (tf.lower() in seen or seen.add(tf.lower()))][:5]
        if not self.timeframes:
            self.timeframes = ["4h", "1d", "1w"]
        self.current_tf = (current_tf or self.timeframes[0]).lower()
        self._rebuild_buttons()

    def _rebuild_buttons(self):
        self.clear_items()
        for tf in self.timeframes:
            style = discord.ButtonStyle.primary if tf == self.current_tf else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=tf.upper(), style=style)

            async def _cb(interaction: Interaction, _tf=tf):
                await self._refresh_chart(interaction, _tf)

            btn.callback = _cb
            self.add_item(btn)

    async def _refresh_chart(self, interaction: Interaction, tf: str):
        try:
            await interaction.response.defer()

            df = fetch_ohlcv_df(self.exchange, self.symbol, tf, limit=200)
            png = render_png(df, title=f"{self.symbol} @ {self.exchange.upper()}  •  {tf.upper()}")
            fname = f"chart_{int(time.time())}.png"
            file = File(io.BytesIO(png), filename=fname)

            last = get_last_price(self.exchange, self.symbol)
            pct24 = get_change_24h_pct(self.exchange, self.symbol)

            emb = interaction.message.embeds[0] if interaction.message.embeds else Embed(title="📈 Gráfica")
            emb.color = color_pct(pct24)
            emb.description = (
                f"**{self.symbol}** en **{self.exchange}**  •  TF **{tf.upper()}**\n"
                f"**Precio:** {fmt_price(last)}   •   **24H:** {fmt_pct(pct24)}"
            )
            emb.set_image(url=f"attachment://{fname}")
            emb.timestamp = datetime.now(timezone.utc)
            emb.set_footer(text=f"{trend_emoji_from(pct24, df)} • actualizado")

            self.current_tf = tf.lower()
            self._rebuild_buttons()

            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=emb,
                attachments=[file],
                view=self
            )
        except Exception as e:
            print(f"[grafica view] error: {e}\n{traceback.format_exc()}")
            try:
                await interaction.followup.send(f"❌ No pude actualizar la gráfica: `{e}`", ephemeral=True)
            except Exception:
                pass
