# Diagnóstico de los logs de sesión de voz (2026-06-10)

Análisis de la activity de la UI (5 capturas). Dos problemas distintos.

## Problema 1: TRANSCRIPCIÓN sale en inglés aunque las settings dicen español

Síntomas en los logs (transcripciones que el usuario dijo en español pero
salieron en inglés): "Really isn't worth it.", "Into the discussion. Oh,
negative one to that.", "Let's see. I was up.", "But sí. Tiempo." (code-switch),
"But sí. Tiempo.".

**CAUSA RAÍZ (estructural, confirmada en código + docs):**
- El STT por default es **Parakeet** (`GEMMA4_STT_ENGINE=parakeet`,
  `pipeline.py:264`), modelo `parakeet-tdt-0.6b-v3`.
- `parakeet_stt.py:171`: el parámetro `language` está **IGNORADO** —
  comentario "Parakeet es multilingüe".
- PERO Parakeet v3 hace **LID (language-ID) INTERNO automático y NO expone token
  de idioma** para forzarlo (doc `sherpa_parakeet_hotwords_nombres_propios.md:56`:
  *"el modelo v3 hace LID interno; no expone 'language token' como Canary, así que
  ese truco de Whisper/Canary no aplica"*).
- → En frases CORTAS o ambiguas, el LID de Parakeet detecta **inglés** y
  transcribe en inglés. `GEMMA4_VOICE_LANG=es` de las settings **NO tiene
  efecto** sobre Parakeet (solo afecta a Whisper, que está de fallback).
- Contradice el diseño documentado de Whisper (`lang_profiles.py:15`,
  `whisper_small_cpu_spanglish_accuracy.md:R6`): "fijar language='es' es la
  best-practice para spanglish con español como matriz". Parakeet rompe eso.

**El selector de idioma en settings (GEMMA4_VOICE_LANG) NO arregla la
transcripción de Parakeet** — solo el reply del LLM y Whisper. Esa es la
desconexión que el usuario notó.

**Opciones de fix (a evaluar, NINGUNA aplicada aún — requiere medición en vivo):**
1. Cuando `GEMMA4_VOICE_LANG` está FIJO (no "auto"), **usar Whisper** (que SÍ
   respeta language='es') en vez de Parakeet. Trade-off: Whisper es ~20× más
   lento (1570ms vs 71ms p50) pero respeta el idioma fijo. Quizá solo cuando el
   usuario fija idioma explícito.
2. Buscar si sherpa-onnx expone algún modo de sesgar el LID de Parakeet v3 (la
   doc dice que NO hay token de idioma; verificar versión actual de sherpa).
3. Post-corrección: detectar transcripción en inglés cuando el idioma fijo es ES
   y re-transcribir con Whisper. Más latencia solo en el caso malo.

## Problema 2: Baxy "falló tanto" con Steam (página de producto)

Síntomas: "ve a la página de Steam de Marvel Spider-Man 2" →
- intento A: `steam(store_page, query="Marvel Spider Man 2")` → dispatched →
  `browser(open steam)` → `browser(goto steam://store/2651280)` → **browser
  failed** → reply "te muestro la hora" (?!) → más browser fallido → cancel_turn.
- intento B: `steam(store_page, appid:"1234567890")` → **steam failed** (appid
  INVENTADO, placeholder) → reply mentiroso "abrí la página directamente
  (aunque no pude confirmar)".

**CAUSAS RAÍZ (varias se combinan):**
1. **El 4B INVENTA el appid.** `store_page` resuelve query→appid solo
   (`steam_store.py:53` busca en la store por término). Pero el 4B pasó
   `appid:"1234567890"` (placeholder obvio) en vez de `query:"Marvel Spider-Man
   2"` → con appid presente el código usa ese (falso). El schema de steam dice
   "Use query/name for game title or appid for direct install" → el 4B se
   confunde y rellena appid con basura. FIX candidato: el schema debe decir
   EXPLÍCITO "NUNCA inventes appid; si no lo conocés pasá query=" + el código
   debería IGNORAR un appid que no parezca real (no-numérico-plausible / longitud
   rara) y caer a query.
2. **Demasiadas tools de navegación** ofrecidas (steam+web+browser_real+browser):
   el 4B encadena steam→browser→browser y se pierde. Es el mismo patrón que el
   fix de navegación-web ya hecho, pero "página de Steam de X" debería liderar
   con steam(store_page, query=) y NO ofrecer browser_real/web.
3. **Reply incoherente/mentiroso** tras el fallo: "te muestro la hora" (de un
   turno previo filtrado) y "abrí la página (aunque no pude confirmar)". El
   primero es contaminación de contexto; el segundo lo debería atrapar el guard
   de honestidad (afirmar acción no verificada).

## Estado

Diagnóstico, NO arreglado (el usuario pidió priorizar entender el porqué).
Ambos problemas son reales y reproducibles desde los logs. Pendientes a atacar
en sesión dedicada (con medición en vivo, regla #3.5):
- P1: política STT idioma-fijo→Whisper (o equivalente).
- P2: anti-invención de appid + liderar steam en "página de Steam de X" +
  honestidad post-fallo.
