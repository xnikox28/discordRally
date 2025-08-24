from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import Embed, Interaction
from discord.ui import View

from comandos.grafica.render import get_change_24h_pct, get_last_price
from comandos.grafica.utils import color_pct, fmt_pct, fmt_price
from data_store import (
    channel_key,
    get_cfg,
    load_db,
    save_db,
    set_channel_param,
)  # 👈 usamos helpers existentes

from .metrics import compute_volatility_24h, refine_params_by_vol


class InfoView(View):
    def __init__(
        self,
        symbol: str,
        exchange: str,
        last: float | None,
        pct24: float | None,
        sigma24: float | None,
        range24: float | None,
        tier_price: str,
        tier_vol: str,
        rec_zz: float,
        rec_tol: float,
        has_applied: bool,  # 👈 NUEVO
    ):
        super().__init__(timeout=900)
        self.symbol = symbol
        self.exchange = exchange
        self.last = last
        self.pct24 = pct24
        self.sigma24 = sigma24
        self.range24 = range24
        self.tier_price = tier_price
        self.tier_vol = tier_vol
        self.rec_zz = rec_zz
        self.rec_tol = rec_tol
        self.has_applied = has_applied

        # ✅ Aplicar preset sugerido
        btn_apply = discord.ui.Button(
            label="✅ Aplicar preset sugerido", style=discord.ButtonStyle.success
        )
        btn_apply.callback = self._on_apply
        self.add_item(btn_apply)

        # 🔄 Refrescar
        btn_refresh = discord.ui.Button(
            label="🔄 Refrescar", style=discord.ButtonStyle.primary
        )
        btn_refresh.callback = self._on_refresh
        self.add_item(btn_refresh)

        # 🗑️ Quitar preset (solo activo si hay preset aplicado)
        btn_remove = discord.ui.Button(
            label="🗑️ Quitar preset",
            style=discord.ButtonStyle.danger,
            disabled=(not self.has_applied),  # 👈 habilitado solo si hay preset
        )
        btn_remove.callback = self._on_remove
        self.add_item(btn_remove)

        # Placeholder
        btn_next = discord.ui.Button(
            label="🚧 Próximamente", style=discord.ButtonStyle.secondary, disabled=True
        )
        self.add_item(btn_next)

    # ---------------- helpers internos ----------------
    def _build_embed(self, emb: Embed, applied_zz: float, applied_tol: float):
        """Reconstruye los campos del embed con los datos actuales (sin volver a pegar consulta de mercado)."""
        emb.title = "ℹ️ Info del par y recomendaciones"
        emb.description = f"**{self.symbol}** en **{self.exchange}**"
        emb.color = color_pct(self.pct24)
        emb.timestamp = datetime.now(timezone.utc)

        emb.clear_fields()
        emb.add_field(name="💲 Precio", value=fmt_price(self.last), inline=True)
        emb.add_field(name="📈 24H", value=fmt_pct(self.pct24), inline=True)
        emb.add_field(name="\u200b", value="\u200b", inline=True)

        vol_txt = (
            f"σ(1h) 24H: **{fmt_pct(self.sigma24)}**\n"
            f"Rango 24H: **{fmt_pct(self.range24)}**"
        )
        emb.add_field(name="🌪️ Volatilidad", value=vol_txt, inline=True)
        emb.add_field(name="🎯 Perfil precio", value=self.tier_price, inline=True)
        emb.add_field(name="🌡️ Perfil vol", value=self.tier_vol, inline=True)

        emb.add_field(name="\u200b", value="\u200b", inline=True)
        emb.add_field(
            name="📐 zigzag_pct",
            value=f"**{self.rec_zz:.3f}**  (~{self.rec_zz * 100:.1f}%)",
            inline=True,
        )
        emb.add_field(
            name="🧲 tolerance",
            value=f"**{self.rec_tol:.3f}**  (~{self.rec_tol * 100:.1f}%)",
            inline=True,
        )

        emb.add_field(
            name="📝 Guía rápida",
            value=(
                "• **Majors (≥ $1)**: zigzag ~3% · tol ~0.2%\n"
                "• **Altcoins ($0.01–$1)**: zigzag ~5% · tol ~0.4%\n"
                "• **Memecoins (< $0.01)**: zigzag ~6% · tol ~0.6%\n"
                "• **Sube** ambos si la vol es alta; **baja** si es muy baja.\n"
            ),
            inline=False,
        )

        emb.add_field(
            name="⚙️ Parámetros aplicados en este canal",
            value=(
                f"Zigzag_pct aplicado: **{applied_zz:.3f}**  (~{applied_zz * 100:.1f}%)\n"
                f"Price_tolerance aplicado: **{applied_tol:.3f}**  (~{applied_tol * 100:.1f}%)"
            ),
            inline=False,
        )
        return emb

    async def _refresh_message(
        self,
        interaction: Interaction,
        *,
        has_applied: bool,
        applied_zz: float,
        applied_tol: float,
    ):
        """Edita el mensaje con embed reconstruido y view nueva (renueva timeout)."""
        emb = (
            interaction.message.embeds[0]  # type: ignore
            if interaction.message.embeds  # type: ignore
            else Embed(title="ℹ️ Info del par")
        )
        emb = self._build_embed(emb, applied_zz, applied_tol)

        new_view = InfoView(
            symbol=self.symbol,
            exchange=self.exchange,
            last=self.last,
            pct24=self.pct24,
            sigma24=self.sigma24,
            range24=self.range24,
            tier_price=self.tier_price,
            tier_vol=self.tier_vol,
            rec_zz=self.rec_zz,
            rec_tol=self.rec_tol,
            has_applied=has_applied,
        )
        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            embed=emb,
            view=new_view,  # type: ignore
        )

    # ---------------- callbacks ----------------
    async def _on_apply(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        db = load_db()
        # guarda las recomendaciones actuales como preset
        set_channel_param(
            db,
            interaction.guild_id,
            interaction.channel_id,
            "zigzag_pct",
            self.rec_zz,  # type: ignore
        )
        set_channel_param(
            db,
            interaction.guild_id,  # type: ignore
            interaction.channel_id,  # type: ignore
            "price_tolerance",
            self.rec_tol,
        )

        await interaction.followup.send(
            f"✅ Preset aplicado:\n• zigzag_pct = **{self.rec_zz:.3f}**\n• price_tolerance = **{self.rec_tol:.3f}**",
            ephemeral=True,
        )
        # Reflejar en la tarjeta
        await self._refresh_message(
            interaction,
            has_applied=True,
            applied_zz=self.rec_zz,
            applied_tol=self.rec_tol,
        )

    async def _on_remove(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        # eliminar claves del canal en state.json
        db = load_db()
        chk = channel_key(interaction.guild_id, interaction.channel_id)  # type: ignore
        cfg = db.get(chk, {})
        changed = False
        for k in ("zigzag_pct", "price_tolerance"):
            if k in cfg:
                del cfg[k]
                changed = True
        if changed:
            db[chk] = cfg
            save_db(db)

        await interaction.followup.send(
            "🗑️ Preset eliminado. Se usarán valores por defecto/recomendados.",
            ephemeral=True,
        )

        # Tras quitar, muestra como “aplicado” los valores recomendados actuales
        await self._refresh_message(
            interaction,
            has_applied=False,
            applied_zz=self.rec_zz,
            applied_tol=self.rec_tol,
        )

    async def _on_refresh(self, interaction: Interaction):
        await interaction.response.defer()
        # Recalcular métricas de mercado (precio/24h/vol) para refrescar tarjeta
        last = get_last_price(self.exchange, self.symbol)
        pct24 = get_change_24h_pct(self.exchange, self.symbol)
        sigma24, range24 = compute_volatility_24h(self.exchange, self.symbol)

        # Recomendar de nuevo en base a estos nuevos datos
        base_zz, base_tol, tier_price = _re_by_price(last)
        rec_zz, rec_tol, tier_vol = refine_params_by_vol(
            base_zz, base_tol, sigma24, range24
        )

        # Actualiza estado interno
        self.last = last
        self.pct24 = pct24
        self.sigma24 = sigma24
        self.range24 = range24
        self.tier_price = tier_price
        self.tier_vol = tier_vol
        self.rec_zz = rec_zz
        self.rec_tol = rec_tol

        # ¿Hay preset aplicado actualmente?
        db = load_db()
        cfg = get_cfg(db, interaction.guild_id, interaction.channel_id)  # type: ignore
        has_applied = ("zigzag_pct" in cfg) or ("price_tolerance" in cfg)
        applied_zz = float(cfg.get("zigzag_pct", self.rec_zz))
        applied_tol = float(cfg.get("price_tolerance", self.rec_tol))

        await self._refresh_message(
            interaction,
            has_applied=has_applied,
            applied_zz=applied_zz,
            applied_tol=applied_tol,
        )


def _re_by_price(last_price: float | None) -> tuple[float, float, str]:
    if last_price is None:
        return (0.05, 0.004, "indeterminado (fallback)")
    p = float(last_price)
    if p < 0.01:
        return (0.06, 0.006, "memecoin ultra barata")
    elif p < 1:
        return (0.05, 0.004, "altcoin mediana")
    else:
        return (0.03, 0.002, "major / alta capitalización")
