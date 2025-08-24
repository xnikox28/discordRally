# Discord Rally Alert Bot (Swing Trading Checklist)

Bot de Discord modular (slash commands) que escanea pares cripto por **canal** y lanza alertas de:
- 🟢 **Posible inicio de rally** (score por confirmaciones)
- 🔴 **Señales de corrección** (para tomar ganancias/salir)

Compatible con **Python 3.13**. Usa `ccxt` (REST) para OHLCV y `discord.py` para comandos.

---

## 🚀 Instalación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # edita TOKEN en .env
```

Invita el bot a tu servidor con permisos de **Application Commands** y **Send Messages**.

---

## 🧠 Cómo funciona

- Cada **canal** tiene su **propia configuración** (símbolo, exchange, timeframes, umbrales).
- Se inicia un **loop de escaneo por canal** con `/start`. Puedes monitorear canales diferentes con criptos distintas.
- El escaneo baja velas con `ccxt`, calcula **EMA20/50/200, RSI, MACD, volumen promedio, mechas**, y aplica la **lógica tipo checklist**:
  - **Rally** (score ≥ `rally_score_needed`):  
    - Cierre > EMA50 > EMA200  
    - EMAs 20/50 ascendentes  
    - RSI ≥ `rsi_rally_min` y subiendo  
    - MACD línea > señal y **histograma aumentando**  
    - Volumen > `vol_spike_mult` × media 20  
  - **Corrección** (dispara si ≥2):  
    - RSI > `rsi_exit_overbought` y cayendo  
    - Histograma MACD **decreciente** ≥ 3 velas  
    - Cierre por debajo de **EMA20**  
    - **Mechas superiores largas** (distribución)

Esto replica el flujo: **1w = mapa**, **1d = confirmación**, **4h = entrada/salida precisa**. De hecho, por defecto los timeframes incluyen `4h,1d,1w`.

---

## 📟 Comandos (slash)

- `/setcoin symbol exchange` — Define símbolo/exchange del **canal** (ej. `WIF/USDT kraken`).
- `/settimeframes 1h,4h,1d,1w` — Lista separada por comas (por defecto: `4h,1d,1w`).
- `/setthresholds rsi_rally_min rsi_exit_overbought vol_spike_mult` — Ajusta umbrales.
- `/setscore value` — Cambia el score mínimo de rally (recomendado 3–4).
- `/cooloff minutes` — Enfriamiento mínimo entre alertas por timeframe/canal.
- `/start` — Inicia el monitoreo en **este canal**.
- `/stop` — Detiene el monitoreo en **este canal**.
- `/status` — Muestra la configuración del canal.
- `/comandos` — Lista **dinámica** de todos los slash commands registrados.

> Tip: Puedes tener varios canales con diferentes criptos y parámetros.

---

## 🧩 Archivos

- `bot.py` — Arranque del bot, registra comandos modularmente.
- `monitor.py` — Loop de escaneo por canal; emite alertas.
- `signals.py` — Indicadores y reglas de rally/corrección.
- `data_store.py` — Persistencia JSON por canal/servidor.
- `comandos/*.py` — Cada slash command en su archivo.
- `.env` — Coloca tu token en `TOKEN`.

---

## ⚠️ Notas

- **No hay ganancias garantizadas.** Son señales técnicas probabilísticas.
- Si recibes muchos falsos positivos, sube `/setscore 4` o endurece umbrales.
- Si un símbolo no existe en un exchange, prueba otro (p.ej. BONK suele estar en bybit).
- El loop usa REST (no websockets), por robustez con Python 3.13.
