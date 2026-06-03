# La capa viva — observador ambiente + perfil de gustos (R-Jarvis, 2026-05-30)

> El usuario pidió que Gemma4 "aprenda quién es el usuario (música, hábitos, gustos)
> y use esa info para darle una mejor experiencia". Esto documenta lo construido,
> con las fuentes verificadas que respaldan cada decisión.

## El problema que resolvía

La capa proactiva del proyecto (behavior_log → pattern_miner → suggestion_queue →
rutina) **ya existía y estaba viva** (15.732 eventos reales medidos, 3 sugerencias
ofrecidas). Pero tenía 2 techos medidos:
1. **Casi ciega**: 15.139 de 15.732 eventos eran `boot`; solo 577 `app_open` — y solo
   de apps que el AGENTE abrió, no lo que el usuario hace a mano.
2. **Mina hábitos, no gustos**: "cerrás Discord al boot" (rutina), no "te gusta el
   rock" (preferencia).

El subagente reactivo NO era la solución: MEDIDO que el 4B lo emite **0/4** en pedidos
que lo justifican (muerto como `skill_load` — el modelo chico no hace meta-pasos).

## La arquitectura (3 capas, respaldada por papers)

### 1. Observador ambiente — `memory_pkg/ambient_observer.py`
Thread daemon que muestrea el comportamiento REAL del usuario. SIN LLM, SIN VRAM
(medido: foreground window = 0.022ms/sample).
- **Música** vía SMTC (`Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager`,
  `winsdk`): artista + título + app, de CUALQUIER reproductor (Spotify, navegador).
  Verificado en vivo (la API responde; lee cuando hay media).
- **App en foco** + dwell vía win32 (proc name, NO título — los títulos filtran
  contenido privado: emails, chats, URLs).
- **Franja horaria** (mañana/tarde/noche/madrugada): ritmo diario.
- Registra solo TRANSICIONES (cambio de app/canción) con duración → no infla el log.
- `context={"source":"ambient"}` distingue del comportamiento que abre el agente.

### 2. Reflexión / perfil — `memory_pkg/taste_profile.py`
Convierte las observaciones crudas en INSIGHTS de quién es el usuario. **Determinista**
(agregación por tiempo/conteo), no LLM: barato, confiable, y CLAUDE.md prohíbe usar
el LLM para clasificar gustos sin necesidad. Patrón observación→insight de
**Generative Agents** (Park et al., arXiv:2304.03442) pero con reflexión determinista.
- Agrega: tiempo por app, app dominante por franja, artistas más escuchados.
- Umbrales anti-ruido (≥10min en una app, ≥3 plays de un artista) → no inventa un
  perfil con 2 datos.
- `build_profile_block()` rinde un PÁRRAFO en lenguaje natural — **Guided Profile
  Generation** (arXiv:2409.13093, +37% en personalización): párrafo NL, no log crudo.
  Etiquetado "NO lo menciones" (anti-parroting).

### 3. Inyección al prompt — `agent.py`
El párrafo entra al system prompt en el bloque ESTABLE (cache-friendly), junto a
project_context. Gate `GEMMA4_TASTE_PROFILE`. Solo el slice relevante, compacto
(<~250 tok) — contexto irrelevante daña al modelo chico (~45%, arXiv:2502.01609).

## Privacidad (table-stakes de la industria, todas implementadas)

La investigación es unánime: la línea no es qué sensor, sino transparencia + control.
- **100% local** (`~/.gemma4/behavior`) — ventaja sobre ChatGPT/Copilot/Google
  (server-side). On-device personalization (Google).
- **Metadata, no contenido**: app/música/ritmo SÍ; títulos de ventana, teclado,
  pantalla, navegación NO (por diseño).
- **Inspectable**: "¿qué sabés de mí?" → muestra el perfil real. Detección por
  EMBEDDINGS (`profile_intent.py`, 18/18 medido), no keywords.
- **Borrable**: "olvidate de mis datos" → PIDE CONFIRMACIÓN (irreversible, CLAUDE.md
  #6) → borra solo lo ambiente (no toca el chat ni el boot).
- **Pausable**: gates `GEMMA4_AMBIENT_OBSERVER=0`, `GEMMA4_JARVIS=0`.

## Detección de intención de privacidad — `memory_pkg/profile_intent.py`
MEDIDO: "¿qué sabés de mí?" lo rutea el router como ACCIÓN (fast_action, 128 tok,
forced-tool-retry) y el 4B devuelve reply VACÍO. Por eso inspect/forget son
short-circuit determinista (tienen respuesta correcta fija, como leer/responder
mensajes). Mecanismo = `accessibility_voice.detect_mode_switch`: centroides
multilingües (es/en/pt/it) + clase `none` + márgenes. **forget es más estricto que
inspect** (floor 0.50 vs 0.42, margen 0.14 vs 0.08): un FP de inspect es inocuo, uno
de forget borraría datos. Hard-negatives: "borrá estos archivos" ≠ borrar el perfil.

## Verificación (mandamiento #3.5 — en vivo, 4B real)
- inspect: *"Esto es lo que aprendí... Las apps que más usás: Code, Spotify. Ritmo:
  a la mañana en Code, a la noche en Spotify. Música: Soda Stereo."* ✓
- forget: pide confirmación → "sí, borralo" → *"Listo, borré (44 observaciones)."* ✓
- inspect tras borrar: *"Todavía no aprendí lo suficiente sobre vos."* ✓
- Tests: 9/9 (`test_jarvis_taste_profile.py`). Suite jarvis/behavior/microagents/
  skills 189/189. Contrato del agente 26/26.

## Gates
`GEMMA4_JARVIS` (master, default ON) · `GEMMA4_AMBIENT_OBSERVER` · `GEMMA4_TASTE_PROFILE`
· `GEMMA4_PROFILE_INTENT_*` / `_FORGET_*` (umbrales del detector).

## Reflexión por LLM — gustos finos (fase 1, 2026-05-30) — `memory_pkg/taste_reflection.py`
Capa OPT-IN que extiende la reflexión determinista: pasa las observaciones agregadas
por el 4B LOCAL para inferir gustos de MÁS ALTO NIVEL ("preferís rock latino de los
90", "programás de día con música de noche") — el paso de reflexión por LLM de
Generative Agents que el diseño reservaba. Verificado en vivo (4B real): sobre
Soda Stereo/Cerati infiere *"rock latino de finales de los 90 / principios de los 2000"*.
- **Gate `GEMMA4_TASTE_LLM_REFLECTION` default OFF**: opt-in. La base determinista
  manda intacta; esta capa AUMENTA, nunca reemplaza.
- **Background, NO per-turn**: el pase LLM corre en un thread daemon cada
  `GEMMA4_TASTE_REFLECTION_TTL_S` (6h); la inyección al prompt sólo LEE un caché en
  disco. (SQLite no es cross-thread → el thread reconstruye su propia conexión.)
- **Guard estructural anti-alucinación**: cada insight DEBE citar (campo `evidencia`)
  una observación REAL; si no referencia ninguna app/artista/franja, se descarta.
  Mide la FORMA (grounding), no confía en el contenido. Precisión > recall.
- **thinking OFF** (MEDIDO: con thinking el 4B gasta el budget en `reasoning_content`
  y devuelve content vacío) + temp 0.3 → JSON limpio.
- **Privacidad**: 4B LOCAL, observaciones AGREGADAS (metadata). Los insights son
  inspectables ("¿qué sabés de mí?" los suma) y borrables (forget limpia el caché).

## Pendiente (no forzado)
- **Más señales**: navegación (títulos de pestaña) suma intereses pero roza privacidad
  — quedó fuera por la regla metadata-no-contenido. Es la decisión del usuario.
- **Precisión de la reflexión**: el guard valida que la EVIDENCIA sea real, no que la
  INFERENCIA se siga de ella (un "death metal" citando un artista real pasaría). Mitigado
  por: insights = contexto de fondo (bajo daño), inspectables y borrables. Subir precisión
  = self-consistency (N corridas) o verify adversarial (1 pase extra). No urgente.
- **Consolidación Mem0** (ADD/UPDATE/DELETE/NOOP, arXiv:2504.19413): si el perfil
  crece, evitar que se infle. Hoy los umbrales + top-N alcanzan.

## Fuentes
- Generative Agents (observación→reflexión→insight) — arXiv:2304.03442
- Guided Profile Generation (+37%, párrafo NL) — arXiv:2409.13093 (EMNLP 2024)
- Mem0 (consolidación de memoria) — arXiv:2504.19413 (ECAI 2025)
- Adaptive Distraction (~45% daño por contexto irrelevante) — arXiv:2502.01609
- SMTC API — https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssessionmanager
- winsdk — https://pypi.org/project/winsdk/
- On-Device Personalization (Google) — https://privacysandbox.google.com/protections/on-device-personalization
