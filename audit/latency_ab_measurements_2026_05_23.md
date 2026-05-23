# Mediciones de latencia A/B (hardware real, RTX, 2026-05-23)

Validación EMPÍRICA de las recomendaciones del informe de investigación, en
NUESTRO hardware (RTX 16GB, E4B-Q4, llama.cpp b9090+). Server de prueba en :8091
(NO se tocó el de prod en :8080).

## 1. -ub 1024 vs 512 (el informe prometía 2-3x): FALSO en nuestra GPU
| ubatch | prefill mediano (7024 tok, sin cache) |
|---|---|
| 512 (actual) | 1682 ms |
| 1024 (propuesto) | 1668 ms |
**Mejora: 1%.** En GPU CUDA con flash-attn ya somos compute-bound; el ubatch
grande ayuda en CPU/Apple Silicon (de donde venía la cita), no acá. NO adoptar
como acelerador; a lo sumo neutro.

## 2. Prefix-cache: el VERDADERO ROI (10x) — CONFIRMADO
| Escenario | Latencia (4224 tok) |
|---|---|
| Turno frío (prefijo nuevo) | 1126 ms |
| Prefijo ESTABLE reusado | 101-114 ms (**10x**) |
| Prefijo CAMBIADO al inicio (= subset de tools cambia) | 1036 ms (paga todo) |

CONCLUSIÓN: el cuello NO es un flag. Es que el system prompt se FILTRA al subset
de tools del router (agent.py:218-222), así el INICIO del prompt cambia turno a
turno y rompe el prefix-cache. Con prefijo estable: 1126->~100ms.

## 3. Tamaño de prompt (decide la estrategia)
| Config | tokens | deja para historial (ctx 16384) |
|---|---|---|
| FULL 65 tools | ~10595 | ~5800 (arriesgado en E4B: modelo se confunde) |
| CORE-SET 15 tools | ~4956 | ~11428 (razonable) |

## Veredicto de implementación (medido)
Mayor ROI: ESTABILIZAR el prefijo del prompt. Arquitectura:
  - CORE-SET fijo (~15 tools comunes) SIEMPRE presente al inicio (cacheable).
  - Extras dinámicos del router APPEND al final (no rompen el prefijo).
  - Resultado esperado: la mayoría de turnos pagan ~100ms de prefill (no ~1100ms).
NO tocar -ub (no rinde en GPU). slot-save-path/keep-alive: menor ROI, opcional.

---
## D-flags: --ctx-checkpoints con swa-full — INFORME CONTRADICHO por el log (2026-05-23)

El informe 1 afirmó que --ctx-checkpoints es INOPERANTE con --swa-full (PR #15293).
PERO el log real (llama-server.err.log, build 9090) muestra lo CONTRARIO:
  "created context checkpoint 1 of 1 ... size = 40.012 MiB"
  "Checking checkpoint with [2850,3873] against 0..."
  "erased invalidated context checkpoint ... n_swa = 512"
-> Los checkpoints SÍ se crean/usan (40 MiB/turno), y n_swa=512 (no 1024 como
   decía el informe para Gemma 4). El informe se equivocó en 2 puntos verificables.
DECISIÓN: NO tocar --ctx-checkpoints a ciegas (ya falló el -ub del mismo informe).
Quitarlo CAMBIARÍA el comportamiento, no es no-op. Requiere A/B dedicado en server
de prueba antes de tocar prod. El sistema funciona (turno mediano 2s); riesgo > ROI.

---
## FR-CoT (thinking estructurado) — MEDIDO en NUESTRO E4B, net negativo (2026-05-23)

Informe thinking-latencia: thinking estructurado ≤4 líneas (INTENT/TOOL/ARGS/GO).
Cifras del informe eran de Qwen2.5; medido en NUESTRO Gemma E4B (smoke E2E):

| categoría | FR-CoT OFF | FR-CoT ON |
|---|---|---|
| apps | 6/6, 6.4s | 6/6, 5.0s ✓ |
| audio | 5/6, 5.2s | 6/6, 2.4s ✓✓ (2x más rápido) |
| **media** | **6/6, 7.3s** | **3/6, 10.5s ✗✗ REGRESIÓN** |

CAUSA de la regresión en media: Gemma E4B a veces emite el formato
'INTENT:.../TOOL:.../ARGS:...' como TEXTO DE SALIDA (no en el canal de
pensamiento) -> rompe el tool-call (tool=False) y suena raro. El informe avisó
que sus cifras eran Qwen, no Gemma. Net negativo -> DEFAULT OFF, opt-in
GEMMA4_FRCOT=1. La mejora en audio (2x) es real pero no compensa romper media.
Para rescatarlo haría falta el router 3-capas + grammar del informe (más trabajo).
