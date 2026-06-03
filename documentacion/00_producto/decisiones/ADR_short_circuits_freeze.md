# ADR — Congelar el treadmill de short-circuits deterministas (2026-06-01)

## Contexto

`_decide_turn` (agent.py) tiene **6 short-circuits deterministas** que responden o rutean
SIN pasar por el LLM:

| short-circuit | qué atrapa | origen |
|---|---|---|
| `arithmetic_shortcircuit` | "cuánto es 47×8" | el 4B calcula mal (MEDIDO: 376→"58.5") |
| `calc_action_shortcircuit` | "suma 2+2 en la calculadora" | type a ciegas sin enfocar la Calc |
| `app_action_shortcircuit` | "escribí X en `<app>`", "ve a X en Discord" | el 4B charlaba/no llegaba a computer_use |
| `app_open_shortcircuit` | "abrí la calculadora" | router no ruteaba app.open consistente |
| `deterministic_reply_shortcircuit` | (acotado) | — |
| `phrase_trigger_shortcircuit` | rutinas del usuario | — |

Cada uno nació de un bug **medido en vivo** (el 4B chico, bajo el techo de 4GB/6GB, es
no-fiable para esas rutas). Son **pragmáticos y cargantes** — borrarlos reintroduce bugs.

## El problema (deuda)

Cada short-circuit nuevo:
- **Pelea con CLAUDE.md regla (b)** ("el LLM responde; nada de hardcodes / árboles if-else").
- Es **regex multi-idioma frágil**: puede mis-disparar o no cubrir un fraseo (cada uno
  costó iteraciones de precisión).
- Mueve inteligencia del LLM a reglas → el asistente se siente menos inteligente si abusa.

El fix profundo (mejor router / modelo más grande) está **bloqueado por los 4GB**. Por eso
los short-circuits se acumulan: es un *treadmill*.

## Decisión

**Congelar en 6.** No se agrega un 7º short-circuit determinista SIN:
1. Una **medición en vivo** que pruebe que el LLM (con el router actual) NO lo hace fiable
   — 3-4 fraseos distintos, no un solo camino (regla #3.5).
2. Confirmar que no lo cubre un short-circuit existente ni una mejora del router/prompt.
3. Subir el techo en `test_shortcircuit_freeze.py` con la justificación + el número MEDIDO.

Preferencias, en orden: **(a) mejorar el prompt/router** para que el LLM lo haga →
**(b) extender un short-circuit existente** → **(c)** recién ahí, uno nuevo.

## Enforcement

`gemma4_agent/tests/test_shortcircuit_freeze.py` falla si aparece un `*_shortcircuit`
nuevo sin subir el techo (mismo patrón que el techo de lazy-imports). El guard cuenta los
eventos de traza `"<nombre>_shortcircuit"` en agent.py.

## Lo que NO decidimos

No **quitamos** los 6 actuales: cada uno tiene su bug medido detrás. Quitar uno exige el
mismo rigor que agregarlo (un gate que pruebe que el LLM ya lo hace solo).
