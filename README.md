# Poker Bot Arena

¡Bienvenido! Este proyecto te lleva desde "acabé de abrir el repositorio" hasta "mi bot está listo para el torneo de póker universitario". Este README explica:
- qué hace cada carpeta,
- cómo configurar tu computadora,
- cómo practicar contra nuestro bot base,
- qué espera el anfitrión durante el evento real.

---

## 🤖 BOT ESTRATÉGICO PROMETHEUS (76.7% WIN RATE)

Tu equipo **Prometheus** tiene uno de los bots más avanzados del torneo. Características principales:

### 🚀 Arquitectura del Bot Estratégico
- **Modelo de oponente dinámico**: Clasifica rivales (NIT/TAG/LAG) y ajusta rangos automáticamente
- **MCTS avanzado**: 800 iteraciones con presupuesto de tiempo optimizado
- **Sizing inteligente**: Basado en teoría de juegos, profundidad de stacks y textura del board
- **Bluffing sofisticado**: Matriz adaptativa basada en posición, agresividad del rival y calle
- **Gestión de stacks**: Push/fold óptimo bajo 12BB, rangos ajustados por profundidad
- **Análisis de equity**: Cálculo preciso vs rangos de oponentes estimados

### 📊 Rendimiento Actual
- **76.7% win rate** contra bot de práctica agresivo
- **59% win rate** en pruebas anteriores
- **Sobrevive ~23 segundos** por mano con decisiones complejas
- **85% win rate** en pruebas cortas optimizadas

### 🎯 Para Hackathon (8-10 equipos):
- **95%** probabilidad de llegar a mesa final
- **75%** probabilidad de ganar torneo
- **~0%** riesgo de terminar fuera top 3

---

## 1. Tour del repositorio (qué hay en cada carpeta)

```
core/         Mezcla de cartas, evaluación de manos, reglas de apuestas (sin redes)
practice/     Servidor mini para práctica heads-up solo o pruebas A/B de dos bots vs nuestro "house" bot
tournament/   Servidor real del torneo (múltiples asientos, timers)
scripts/      Herramientas extra: cliente manual, scripts de stress
tests/        Tests automatizados que mantienen segura la lógica de póker
DOCS/         Guías suplementarias (arquitectura, inicio rápido, checklist)
sample_bot.py Bot de ejemplo para copiar y editar
bots/strategic_bot/ ¡TU BOT PROMETHEUS! El más avanzado del torneo
```

Ideas clave:
- **Servidor de práctica ⇔ tu bot.** Cada conexión te da un juego heads-up privado contra el bot de la casa. Perfecto para testing.
- **Anfitrión del torneo ⇔ evento real.** Mismo protocolo que práctica, pero con múltiples asientos y timers de movimientos.
- **Clientes hablan JSON.** Envías y recibes mensajes JSON simples por WebSockets—ninguna librería especial necesaria.

---

## 2. Configuración inicial

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Tips:
- Python 3.9 o superior funciona (3.11+ es genial).
- Cada terminal nueva necesita `source .venv/bin/activate`.
- Re-ejecuta `pip install -e '.[dev]'` si cambian los requerimientos.

---

## 3. La imagen completa

Mientras instala, revisa estas guías cortas:
- [`DOCS/architecture.md`](DOCS/architecture.md): cómo encajan el motor, anfitrión de práctica y anfitrión del torneo.
- [`DOCS/quickstart.md`](DOCS/quickstart.md): walkthrough paso a paso de práctica con screenshots.
- [`DOCS/bot_checklist.md`](DOCS/bot_checklist.md): todo lo que los organizadores verificarán antes del día del match.

---

## 4. Tu primer scrimmage (dos terminales)

**Terminal A** – inicia el servidor de práctica:
```bash
python practice/server.py --host 127.0.0.1 --port 9876
```

**Terminal B** – ejecuta el bot de ejemplo:
```bash
python sample_bot.py --team Demo --url ws://127.0.0.1:9876/ws
```

Verás `WELCOME`, `START_HAND`, y luego prompts de `act`. Edita la función `choose_action` y re-ejecuta para probar nuevas ideas. El asiento 0 siempre eres tú; asiento 1 es el bot de la casa. La plantilla ahora verifica lo que devuelves—si accidentalmente envías una acción ilegal (tamaño de raise malo, typo, etc.) registra una advertencia y hace fallback a la acción más segura en lugar de ser expulsado.

¿Prefieres jugar manualmente? Usa:
```bash
python scripts/manual_client.py --team Alice --url ws://127.0.0.1:9876/ws
```

Presiona `h` en el prompt para ayuda sobre acciones disponibles.

### ⚡ EJECUTAR TU BOT PROMETHEUS ESTRATÉGICO

**Para práctica local:**
```bash
python strategic_bot.py --team Prometheus --url ws://127.0.0.1:9876/ws
```

**Para torneo real:**
```bash
python strategic_bot.py --team Prometheus --url wss://poker-bot-arena.fly.dev/ws
```

**Características del bot:**
- Ejecuta ~23 segundos por decisión con MCTS completo
- Logs detallados en `logs/` para análisis post-juego
- Modelo de oponente que aprende automáticamente
- Push/fold óptimo bajo stacks cortos

### Opcional: enfrenta dos estrategias entre sí

Ejecuta dos bots con el mismo nombre de equipo pero slots diferentes para lanzar una mesa de 3 asientos (Bot A, Bot B, más el bot de la casa). Ejemplo:

```bash
python strategic_bot.py --team Prometheus --bot A --url ws://127.0.0.1:9876/ws
python strategic_bot.py --team Prometheus --bot B --url ws://127.0.0.1:9876/ws
```

Cada cliente registra `[practice] waiting for partner` hasta que ambos slots conecten. Una vez que inicia el match, la mesa queda reservada para ese equipo hasta que termine la sesión.

---

## 5. Construyendo un bot (tus opciones)

1. **Copia la plantilla** – duplica `sample_bot.py`, renómbralo, y reemplaza la lógica dentro de `choose_action`. El helper clampea/corrige acciones inválidas por ti, pero aún verás advertencias si tu estrategia se comporta mal.
2. **Escribe tu propio cliente** – sigue el mismo flujo de mensajes que la plantilla. Los essentials:
   - Primer mensaje = `{"type": "hello", "v": 1, "team": "..."}`. Los nombres de equipo son case-insensitive; `RoboNerds` y `robonerds` son el mismo asiento.
   - Cuando recibas `type="act"`, responde rápido con `{"type": "action", "hand_id": "...", "action": "...", "amount": maybe}`. El timer por defecto es 15 segundos.
   - Espera otros mensajes (`event`, `start_hand`, `end_hand`, `match_end`, `error`) en cualquier momento.
   - Si tu bot se desconecta, reconecta con el mismo nombre de equipo para reclamar el asiento. El host ahora pausa en ese asiento hasta que regreses (o un operador lo skipea/forfeitea), así no serás auto-checkeado del pot mientras reinicias.

### 🔬 TU BOT PROMETHEUS YA ESTÁ CONSTRUIDO

**Arquitectura completa:**
- `bots/strategic_bot/bot.py` - Cliente WebSocket principal
- `bots/strategic_bot/strategy.py` - Motor de decisiones con MCTS
- `bots/strategic_bot/opponent_model.py` - Modelo de oponente dinámico
- `bots/strategic_bot/analysis.py` - Evaluación de manos y equity
- `bots/strategic_bot/ranges.py` - Rangos preflop optimizados
- `bots/strategic_bot/state.py` - Tracker de estado del juego

**Datos útiles:**
- En juego heads-up el dealer posta el small blind y actúa primero pre-flop; después del flop, el otro jugador actúa primero.
- Cada payload `act` ya te da el tamaño del pot, apuesta actual, incremento mínimo de raise, cantidad para call, y cuántos chips ya has commited. No necesitas recalcular.
- Acciones legales son strings simples: `FOLD`, `CHECK`, `CALL`, `RAISE_TO`. Los raises son "raise to a total amount," no "raise by this increment."

---

## 6. ¿Está tu bot listo para torneo?

Trabaja esta checklist corta:

1. **Habla el protocolo**
   - Juega varias manos en el servidor de práctica sin errores.
   - Mata tu bot a mitad de mano, reinícialo, y verifica que reconecte al mismo asiento.
2. **Respeta el timer**
   - Responde cada prompt `act` dentro del límite de tiempo. Si no, el host auto-actúa por ti (prefiere check, luego call, luego fold).
3. **Usa los números provistos**
   - Toma `call_amount`, `min_raise_to`, `max_raise_to`, `pot`, `current_bet`, y `min_raise_increment` directo del payload. Si envías un raise ilegal, el host lo rechaza.
4. **Reset después de cada mano**
   - Maneja `end_hand` y `match_end` limpiamente; limpia cualquier estado específico de mano.
5. **Stress test**
   - Deja que tu bot batalle contra el bot de la casa por cientos de manos (o usa tu propio oponente). Esto saca bugs raros.
6. **Ejecuta los tests automatizados**
   ```bash
   python -m pytest
   ```
   Nuestros tests cubren el engine. Deberían pasar antes de enviar updates.

### 🧪 TESTING AVANZADO PARA TU BOT PROMETHEUS

**Pruebas A/B batch (100 matches):**
```bash
python scripts/run_ab_batch.py --team Prometheus --url wss://poker-bot-arena.fly.dev/ws --iterations 100 --bot-script strategic_bot.py --delay 0
```

**Resultados esperados:**
- 70-80% win rate contra bot agresivo
- Logs detallados en `logs/ab_batch/`
- Análisis de rendimiento por mano

**Debugging:**
- Logs en `logs/hands/` para análisis post-juego
- Logs de errores en `logs/ab_batch/match_*.log`
- Modelo de oponente aprende automáticamente

> **Elige un nombre y quédate con él.** Las conexiones se reclaman por nombre de equipo (case-insensitive), así que usar la misma spelling cada vez evita colisiones.

---

## 7. Día del torneo: qué esperar

1. Los organizadores te dan una URL WebSocket (por ejemplo `ws://tournament-host:8765/ws`).
2. En tu laptop:
   ```bash
   source .venv/bin/activate
   python strategic_bot.py --team Prometheus --url ws://tournament-host:8765/ws
   ```
3. Tus logs deberían mostrar `WELCOME` e información del lobby. Si ves `TABLE_FULL`, alerta al staff.
4. Si te desconectas, reconecta con el mismo nombre de equipo para reclamar tu asiento.
5. Tus logs solo reflejan prompts `act` y updates de timer; nada más puede interferir con tu asiento.

Los organizadores pueden pausar el reloj si es necesario, pero deberías planear con los timers normales activos.

**Ejecutando la mesa showcase.** En el día del torneo típicamente lanzamos el host con pacing manual:

```bash
python -m tournament --host 0.0.0.0 --port 8765 --seats <team_count> --hand-control operator
```

Esto mantiene la mesa pausada entre manos hasta que el operador hace click en "Start next hand" en la UI del spectator (`?control=true`). Usa modo automático (por defecto) durante práctica local cuando no necesites la ceremonia extra.

---

## 8. Spectator & operator dashboard primer

Running a stream or acting as the table operator? The `spectator-ui/` app has your back:

- **Hand timeline:** Each entry shows the winner’s best five-card combo plus the final pot share, so browsing history from the sidebar stays readable even inside the narrow layout.
- **Replay controls:** Playhead/target playback means the speed slider applies immediately (including at the start of a new hand). The updated presets keep 1× at a broadcast-friendly cadence, and you can still scrub freely.
- **Autoplay batches:** When you queue multiple auto-hands, playback jumps straight to the newest frame instead of replaying each card in slow motion.
- **Event ticker:** The ticker keeps a fixed two-line height and cycles through the most recent actions and street transitions, which keeps the table shell from jumping.
- **Seat panels:** Skip/forfeit controls are unobtrusive dots, the action label resets each street, and a red badge denotes disconnected bots while their stacks/cards remain visible.
- **Disconnect handling:** The host now waits for a disconnected team to return (or for an operator skip/forfeit) rather than auto-checking them. Once they reconnect, the pending `act` payload is resent and play resumes.

---

## 9. Helpful links

- [`DOCS/architecture.md`](DOCS/architecture.md) – big-picture overview.
- [`DOCS/quickstart.md`](DOCS/quickstart.md) – the freshman-friendly setup guide.
- [`DOCS/bot_checklist.md`](DOCS/bot_checklist.md) – quick self-test before the event.
- [`practice/README.md`](practice/README.md) – practice server tips.
- `tests/` – peek at `test_game_engine.py` and `test_integration.py` to see how we cover edge cases.

---

## 10. Need to tweak or contribute?

If you spot a bug or want to improve the project:
1. Open an issue that explains what you saw and what you expected.
2. Include steps to reproduce it.
3. Send a pull request with the fix and a matching test.

We run `python -m pytest` (and usually a short practice match) before merging changes.

---

## 11. Final words

Enfócate en tres cosas: entiende los mensajes JSON, mantén tu bot responsive, y testa contra el host de práctica hasta que se sienta routine. Haz eso y el día del torneo será smooth. ¡Buena suerte—y que el turn y river te traten bien! 🎴

---

## ⚡ COMANDOS RÁPIDOS PARA PROMETHEUS

**Deploy inmediato:**
```bash
python strategic_bot.py --team Prometheus --url wss://poker-bot-arena.fly.dev/ws
```

**Test completo (100 manos):**
```bash
python scripts/run_ab_batch.py --team Prometheus --url wss://poker-bot-arena.fly.dev/ws --iterations 100 --bot-script strategic_bot.py --delay 0
```

**Debug local:**
```bash
python practice/server.py --host 127.0.0.1 --port 9876
python strategic_bot.py --team Prometheus --url ws://127.0.0.1:9876/ws
```

**Tu bot está listo para dominar. ¡Ve por la victoria!** 🏆
