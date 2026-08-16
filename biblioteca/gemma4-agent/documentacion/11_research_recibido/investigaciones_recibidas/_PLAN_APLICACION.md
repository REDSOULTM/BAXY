# Plan de aplicación de las 8 investigaciones — estado y siguiente paso

Realidad medida: las 8 investigaciones (~4000 líneas) tienen cambios mayormente
de esfuerzo MEDIO/ALTO que tocan arquitectura. Aplicarlas bien (verificar+medir+
tests, sin romper) es trabajo de VARIAS sesiones. Se van haciendo de a una, cada
una commiteada y medida bajo vram4. Este archivo traza el progreso para retomar.

## HECHO (medido, commiteado)
- **Inv 1 — sampling greedy dual** ✅ APLICADO. Greedy (temp=0,top_k=1) en turno
  de acción + forced-retry; defaults en conversación. Gate GEMMA4_GREEDY_TOOLCALL.
  MEDIDO: −15-18% latencia (apps 5.2→4.6s, audio 3.8→3.1s), 12/12 mantenido.
  Hallazgo: el "2/6 sin thinking" NO se reproduce con comandos crisp+tools claras
  → prefill/few-shot (palancas 2-3) DESCARTADAS (sin problema medible).
  Detalle: audit/inv1_toolcalling_medido_2026_05_23.md

## PENDIENTE (orden de impacto/ROI por hora)

### Inv 2 — memoria + entity-grounding (P0 alto valor, esfuerzo Medio)
Ataca el bug "mamá→grupo Música". Movimientos:
- P0: distinguir contacto-vs-grupo en la resolución (la causa del bug). [medio]
- P0: resolver entidad a top-k candidatos ANTES del LLM + que elija de la lista
  (no string libre). [medio — toca el protocolo de tool args]
- P1: memoria 3 capas (core pinned ≤6 / retrieval sqlite-vec+EmbeddingGemma /
  episodic con salience+TTL). [medio — nueva dependencia EmbeddingGemma 308M]
- P1: salience+TTL+filtro anti-test-junk al escribir memoria. [bajo]
PARCIAL YA HECHO (sesión previa): _verify_chat_header OCR (cubre el síntoma:
aborta si el chat abierto no es el contacto). Falta la cura de raíz (contacto vs
grupo + resolución por ID).

### Inv 3 — verificación de acciones + recovery (esfuerzo Medio, 828 líneas)
Confirmar efecto real (UIA en vez de re-OCR), recovery sin mentir, verificación
selectiva por riesgo. Cruza con el sistema de verifiers que ya existe.

### Inv 4 — contexto/historial multi-turno (esfuerzo Medio, 426 líneas)
Compaction sin romper cache, qué tool_results retener, presión de contexto cerca
de 16K.

### Inv 5 — Jarvis proactivo (esfuerzo Medio-Alto, 351 líneas) ⭐ visión de RED
Capa A: detección barata de patrones (conteo+umbral ≥5 reps/≥7 días, consistencia
≥0.6). Capa B: PrefixSpan NOCTURNO (cron, fuera del loop) para rutinas compuestas.
Oferta en "breakpoint" (fin de boot, silencio mic), no a media tarea (Horvitz 1999
act/ask/wait). Engancha al routine_tool existente (ya tiene on_app_open/cron/etc).
LLM solo conversa la sugerencia; la minería es CÓDIGO determinista (cabe en vram4).

### Inv 6 — estabilidad/no-crash (esfuerzo Medio-Alto, 919 líneas)
vram_watchdog.py (warn 800/degrade 500/critical 250 MiB → unload_mmproj + bajar
ctx a 8192). /health miente bajo carga → usar /slots?fail_on_no_slot=1 + heartbeat.
Aislamiento de tools. El más largo; varios sub-fixes independientes.

### Inv 7 — NLU multi-intent/clarificación (esfuerzo Medio, 329 líneas)
"abrí Spotify y bajá el volumen" (2 acciones), "mandale a Juan" (slot faltante).
Descomponer multi-intent en código antes del LLM; clarificación de una pregunta.

### Inv 8 — automatización GUI/UIA (esfuerzo Medio-Alto, 457 líneas)
UIA tree (elementos por nombre/rol/AutomationId) como camino primario vs OCR/
visión cara. Macros deterministas parametrizadas. Reduce dependencia de mmproj.

## Metodología por cada una (regla de RED)
Leer inv + código real → verificar contra build (los informes fallan en detalles)
→ gate (qué medir) → cambio mínimo → smoke_e2e bajo vram4 → commit/opt-in/revertir.
Server: arrancar con `llama-server --models-preset router_presets_vram4.ini
--models-max 1 --port 8080 --no-webui` (RED dio acceso total a la PC).
