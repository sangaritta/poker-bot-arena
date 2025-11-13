# Inicio Rápido para Estudiantes

¡Hola! Esta página es la manera más rápida de ir desde un clone fresco hasta un bot que puede jugar manos. No se requiere experiencia previa en software de póker.

---

## 1. Clona el repo e instala herramientas

Abre una terminal y ejecuta:
```bash
git clone <repo-url>
cd poker-bot-arena
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```
El último comando instala la librería WebSocket y las herramientas de test que usamos.

---

## 2. Inicia el servidor de práctica

Este servidor da a cada bot conectando su propio match heads-up contra el bot house integrado.
```bash
python practice/server.py --host 127.0.0.1 --port 9876
```
Deja esta ventana de terminal corriendo—jugarás contra ella desde otra ventana.

---

## 3. Ejecuta el bot de ejemplo (solo o pares A/B)

Abre una segunda terminal, activa el virtual environment de nuevo, y ejecuta:
```bash
source .venv/bin/activate
python sample_bot.py --team MyBot --url ws://127.0.0.1:9876/ws
```
Deberías ver mensajes como `WELCOME`, `START_HAND`, y `act`. El bot ya conoce el protocolo; solo necesitas cambiar la lógica de decisión en `choose_action`. La plantilla ahora protege contra movimientos ilegales—si tu código pide una acción inválida, registra una advertencia y hace fallback a un check/call/fold seguro en lugar de dejar que el host te expulse.

¿Quieres comparar dos estrategias head-to-head mientras el bot de práctica observa? Lanza un segundo cliente con el mismo `--team` pero pasa `--bot A` en el primer proceso y `--bot B` en el segundo:

```bash
python sample_bot.py --team MyBot --bot A --url ws://127.0.0.1:9876/ws
python sample_bot.py --team MyBot --bot B --url ws://127.0.0.1:9876/ws
```

El server espera hasta que ambos slots conecten, luego abre una mesa de 3 asientos (A vs B vs house). Si uno se desconecta mid-match, reconecta con el mismo label `--bot` para reclamar el asiento.

---

## ⚡ EJECUTAR TU BOT PROMETHEUS

Para práctica local:
```bash
python strategic_bot.py --team Prometheus --url ws://127.0.0.1:9876/ws
```

Para torneo real:
```bash
python strategic_bot.py --team Prometheus --url wss://poker-bot-arena.fly.dev/ws
```

**Características del bot:**
- 76.7% win rate vs bot agresivo
- Modelo de oponente que aprende automáticamente
- MCTS avanzado (800 iteraciones)
- Logs detallados para análisis

---

## 4. Prueba una mano tú mismo

¿Quieres hacer click en botones y ver el protocolo en acción? Usa el cliente manual:
```bash
python scripts/manual_client.py --team Alice --url ws://127.0.0.1:9876/ws
```
Escribe `h` en el prompt para ver qué significan los movimientos legales. Esto usa los mismos mensajes exactos que recibe tu bot.

---

## 5. Itera en tu estrategia

- Agrega `print()` o logging dentro de `choose_action` para poder revisar por qué el bot hizo cada movimiento.
- Mantén tus propias notas sobre el hand id (`hand_id`), tamaños de stack, y cartas community—todo eso se envía en el payload `act`.
- Si pierdes conexión, simplemente reinicia con el mismo `--team`; el practice server y tournament host ambos reconocen el nombre (case-insensitive) y te dejan reclamar el asiento.

---

## 6. Cuando estés listo, alcanza el tournament host

Para ensayar la experiencia on-stage (timers más controles de override manual), inicia el tournament host:
```bash
python -m tournament --manual-control
```
`--manual-control` apaga los timeouts automáticos para que un operador pueda forzar skips—útil durante eventos live. La mayoría de equipos se quedan en el practice server hasta que su bot es estable, luego corren algunos matches en el host completo para double-checkear comportamiento.

---

## Recordatorios amigables

- Mantén tu bot stateless entre manos; el host te dice todo lo que necesitas.
- Siempre responde a `act` rápido—los organizadores lo esperan incluso durante práctica.
- Elige un nombre de equipo y quédate con él—las conexiones se matchean por nombre (case-insensitive).

¡Feliz hacking! Si algo se siente poco claro, contacta a los organizadores o abre un issue—estamos aquí para ayudar.☴

---

## 🧪 TESTING AVANZADO PARA TU BOT

**Pruebas batch A/B (100 matches):**
```bash
python scripts/run_ab_batch.py --team Prometheus --url wss://poker-bot-arena.fly.dev/ws --iterations 100 --bot-script strategic_bot.py --delay 0
```

**Resultados esperados:**
- 70-80% win rate
- Logs en `logs/ab_batch/`
- Análisis de rendimiento por mano
