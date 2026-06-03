# Optimización de latencia — cache de microagents (Fase 4) 2026-05-21

## Hallazgo (cProfile)

Perfilé `Gemma4Agent._system_message()` — corre en CADA turno para armar el
system prompt — con cProfile sobre 200 builds (sin LLM, GPU ocupada). Costo total
**2.08 ms/turno**. Top del perfil:

```
ncalls  cumtime  per   función
   200   0.227  1.13ms build_microagents_section  <-- 54% del costo
   200   0.153  0.77ms   load_microagents
  1400   0.106         read_text   <-- 7 archivos × 200 turnos
  2800   0.062         nt.stat
   200   0.094  0.47ms load_context (project_context)
```

**Causa raíz:** `build_microagents_section` (en `_system_message`) llamaba
`load_microagents()`, que re-leía y re-parseaba TODOS los `*.md` de
`microagents/` desde disco EN CADA TURNO. El cache existente (`cached=`) solo
evitaba re-*matchear*, no re-*leer*. 1400 `read_text` + 2800 `stat` en 200 turnos.

## Fix (bajo riesgo, comportamiento preservado)

Cache de `load_microagents()` por una **firma stat-only del directorio**:
`{(filename, mtime_ns, size)}` de cada `*.md`. Recomputar la firma es solo stat
(barato); se re-lee el cuerpo SOLO cuando la firma cambia. Preserva el live-edit
(agregar/editar/borrar un microagent se refleja al siguiente turno — la firma
cambia) que era el motivo de re-leer cada turno.

## Medición antes/después

| métrica | antes | después |
|---------|-------|---------|
| `load_microagents()` warm | 1.16 ms (re-lee) | **0.20 ms** (solo stat) — 6× |
| `_system_message()` warm | 2.08 ms | **1.06 ms** — 49% |

Ahorro: **~0.95 ms/turno** en el armado del prompt. En un presupuesto de voz de
4-5 s es chico en absoluto, pero es una ganancia PURA (sin cambio de
comportamiento, verificado por test_microagents_cache + las 27 tests de
microagents previas siguen verdes) y elimina ~7 reads de disco por turno en el
hot-path.

## Veredicto contra el norte rector

✅ LATENCIA: −49% en `_system_message`, −7 reads de disco/turno.
✅ FIABILIDAD: live-edit preservado (firma mtime/size invalida el cache);
   test_microagents_cache pinea edit/add/remove → re-read.
✅ ARQUITECTURA: cache local al módulo, sin estado compartido nuevo, sin tocar
   el contrato de `load_microagents`/`build_microagents_section`.

## Lo que NO optimicé (y por qué)

- `project_context.load_context()` (0.47 ms/turno): re-lee GEMMA4.md cada turno
  por el mismo motivo (live-edit). Mismo fix aplicaría, pero el costo es la mitad
  del de microagents y, sin un GEMMA4.md presente (caso común), es solo ~8 stats
  (246 µs). Bajo payoff; lo dejo salvo que RED lo pida. Anotado, no aplicado.
- El `_EMBED_CACHE_ORDER.remove(key)` O(N) del LRU de semantic_router: N≤256,
  microsegundos, no vale la complejidad de cambiarlo a OrderedDict.
- El costo dominante real del turno es el LLM (prefill+decode en GPU), no medible
  acá por la GPU ocupada. Lo Python-side recuperable era esto.
