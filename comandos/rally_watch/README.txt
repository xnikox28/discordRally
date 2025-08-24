# Rally Watch (Slash Command)

Carpeta drop-in para `discordBot/comandos/rally_watch`.
- Comando: `/rallywatch` (o `!rallywatch` si usas hybrid commands).
- Botones: **Activar TODAS** / **Desactivar TODAS** (15m,30m,1h,4h,1d).
- Data provider: Coinbase (primario) con fallback a CoinGecko.

## Integración
1) Copia la carpeta `rally_watch` a `discordBot/comandos/`.
2) Asegúrate de tener `pandas` y `requests` instalados.
3) En tu loader: `await bot.load_extension("comandos.rally_watch")`
4) En Discord: ejecuta `/rallywatch` y usa los botones.

## Configuración
- Edita `storage.py` para símbolos por defecto, polling, multiplicador de Keltner, fuente de datos.
- Símbolos tipo `BTC-USD`, `BONK-USD`. CoinGecko usa el identificador del coin (ej: `bonk`, `bitcoin`).

## Notas
- Coinbase no ofrece 4H nativo; se obtiene desde 1H con **resample**.
- CoinGecko OHLC no incluye volumen detallado; se aproxima con `market_chart` por hora.
