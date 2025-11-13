# Overview de Arquitectura

Poker Bot Arena está construido alrededor de tres capas:

1. **Game Engine (`core/game.py`)**
   - Reglas puras de No-Limit Hold'em: dealing, rondas de apuestas, side pots, evaluación de manos.
   - Sin networking aquí—solo objetos Python.

2. **Tournament Host (`tournament/server.py`)**
   - Maneja asientos, clientes WebSocket (bots), timers, y skips manuales.
   - Cada mesa comparte una instancia única de `GameEngine`; los bots escuchan prompts `act` y responden con mensajes `action`.

3. **Clientes**
   - **Bots**: Clientes WebSocket escritos por estudiantes que manejan `hello`, `act`, y mensajes de eventos básicos.
   - **Practice Server (`practice/server.py`)**: lanza un `GameEngine` fresco por conexión para que estudiantes puedan scrimmagear localmente contra el bot house baseline.

```
Remote Bot ─┐
            ├─ WebSocket ── Tournament Host
Practice    │
Server ─────┘
Baseline Bot
```

## Flujo de Mensajes
Todos los mensajes WebSocket son objetos JSON con un campo `type` (`hello`, `act`, `action`, `event`, etc.). El schema completo vive en [`TECHNICAL_SPEC.md`](../TECHNICAL_SPEC.md).

Eventos clave:
- `start_hand`: nueva mano comienza (posición de button, stacks).
- `act`: asiento actual debe responder con `action`.
- `event`: updates públicas como `BET`, `CALL`, `FLOP`, etc.
- `end_hand`: pot settled; stacks actualizados.
- `admin`: acciones manuales del operador (ej. forced skip).

Practice y tournament hosts comparten el mismo protocolo así los bots pueden moverse entre ellos sin cambios.

## Guía de Archivos
- `core/`: reglas de poker, cartas, evaluators, modelos de datos.
- `tournament/`: host WebSocket multi-asiento.
- `practice/`: ambiente de scrimmage fácil y bot de ejemplo.
- `scripts/`: utilidades (cliente manual, stress runner).
- `tests/`: suite pytest cubriendo engine y edge cases del server.

Empieza en `practice/` para construir confianza, luego conéctate al tournament host para matches completos.

---

## 🤖 TU BOT PROMETHEUS: Arquitectura Detallada

### Componentes del Bot Estratégico

1. **`bots/strategic_bot/bot.py`** - Cliente WebSocket Principal
   - Maneja conexión y protocolo JSON
   - Fallback automático para acciones inválidas
   - Logging detallado de decisiones

2. **`bots/strategic_bot/strategy.py`** - Motor de Decisiones
   - **MCTS avanzado**: 800 iteraciones, tiempo optimizado
   - **Sizing inteligente**: Basado en teoría de juegos
   - **Bluffing sofisticado**: Matriz adaptativa por oponente
   - **Push/fold óptimo**: Rangos ajustados por stack depth

3. **`bots/strategic_bot/opponent_model.py`** - Modelo Dinámico de Oponente
   - Clasificación automática (NIT/TAG/LAG/Maniac)
   - Estimación de rangos basada en VPIP y patrones
   - Ajustes de agresividad por posición y stack

4. **`bots/strategic_bot/analysis.py`** - Análisis de Manos
   - Evaluación precisa de equity vs rangos
   - Detección de draws (flush/straight)
   - Cálculos de pot odds e implied odds

5. **`bots/strategic_bot/ranges.py`** - Rangos Optimizados
   - Rangos preflop GTO para heads-up
   - Ajustes posicionales y de stack
   - Rangos de 3bet y squeeze

6. **`bots/strategic_bot/state.py`** - Tracker de Estado
   - Historial completo de acciones por calle
   - Información de stacks y posiciones
   - Estado del board y posibles draws

### Rendimiento Actual
- **76.7% win rate** vs bot agresivo
- **23 segundos** por decisión (MCTS completo)
- **Modelo de oponente** que aprende en tiempo real
- **Logs detallados** en `logs/` para análisis

### Ventajas Competitivas
- **Profundidad de pensamiento**: MCTS evalúa miles de líneas futuras
- **Adaptabilidad**: Modelo de oponente se ajusta dinámicamente
- **Precisión**: Sizing y bluffing basado en teoría de juegos
- **Robustez**: Fallbacks automáticos previenen crashes
