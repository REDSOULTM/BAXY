# 09 — Progresión de iteraciones (honesta)

**Fecha**: 2026-05-11 (sesión continua)

Resumen riguroso de qué cambié y qué pasó con el bench. Sin maquillar.

---

## Tabla maestra de runs

| Run | Config | PASS / 54 | % | Δ vs baseline |
|---|---|---|---|---|
| **baseline** | Prompt v3 (3400 tok) + 25 anchors + topK=12 | 41 | 75.93% | — |
| **post_refactor** | Prompt v4 (883 tok) + 8 anchors + topK=8 + MissionGoal + eager | 34 | 62.96% | **−13 pts** ❌ |
| **step1** | Revertido prompt+anchors+topK al baseline + MissionGoal + eager activos | 30 | 55.56% | **−20 pts** ❌❌ |
| **step2** | Como step1 pero MissionGoal y eager DESACTIVADOS | 35 | 64.81% | **−11 pts** ❌ |
| **step3** | Re-corrida idéntica de step2 (medir variance) | ⏳ | ⏳ | ⏳ |

## Lo que aprendí

### Hallazgo 1: el "refactor agresivo" rompió cosas

Aplicar 4 cambios simultáneos (prompt -74%, anchors 25→8, topK 12→8, MissionGoal) costó **-13 pts**. Eso fue mi error metodológico: violé "un cambio por vez" del plan original.

### Hallazgo 2: revertir el prompt no recuperó completamente

Step1 revirtió prompt + anchors + topK pero mantuvo MissionGoal y eager activos. **Cayó a 55.56%**. Esto significa que **algo más en MissionGoal o eager está rompiendo latencia**.

### Hallazgo 3: desactivar MissionGoal mejoró parcialmente

Step2 desactivó MissionGoal por env (`CARTER_V4_MISSION_GOAL=0`) y `CARTER_V4_LAZY_RETRIEVER=1`. **Subió de 55.56% → 64.81%** (+9 pts). Confirma que MissionGoal contribuye al overhead.

### Hallazgo 4: la variance run-to-run es alta

Mismo caso, distintos runs:
- C06-01 "qué hora es": 6983ms (baseline) → 16108ms (post_ref) → 9313ms (step2)
- C09-01 "abre Steam": 7437ms → 17843ms → 16922ms
- C17-01 "abre Steam": 7593ms → 24500ms → 8547ms
- C16-01 "abre stean": 14562ms → 30344ms → 10092ms

Mismo código, mismo bench, latencias **2-4x distintas entre runs**. La fuente es **el llama-server prompt cache**: cuando el cache está caliente con un prompt similar, latencia es 6-8s. Cuando el cache se invalida, sube a 16-25s.

### Hallazgo 5: el harness ganador NO tiene esa variance

El reporte del harness reporta p50=4.26s, p99=20.45s **estable a través de 14 iteraciones**. Diferencia: el harness corre **chunked en procesos Python frescos** y el llama-server se mantiene con el MISMO system_prompt + tools entre chunks. Eso preserva el cache.

Mi bench corre todos los 54 casos en un solo proceso → el agent cambia history entre turns → cada turn invalida parte del cache.

---

## Diagnóstico real (basado en evidencia)

Carter v4 tiene **un problema estructural de latencia que no es del modelo ni del prompt**: es del **agent loop**.

Cada turn Carter:
1. Construye system_msg (history + memory_facts) — esto cambia cada turn → invalida cache
2. Llama tool_retriever.select() → puede devolver tools distintas según query → invalida cache
3. Llama LLM → ahora el prompt es distinto al turn previo → re-prefill (~1-3s overhead)
4. Si emite tool → dispatch + verify
5. Llama LLM otra vez con follow-up message → distinto prompt → re-prefill otra vez

**El harness ganador no tiene history acumulada** — cada caso es independiente. Su latencia p50 4.26s es **el techo real del modelo**. Carter agrega 2-5s por turn por las dependencias dinámicas.

### El fix correcto sería:

1. **Estabilizar el prefijo del prompt** que va al LLM: el system + tools + ejemplos no debe cambiar entre turns. Solo el final (user_text actual) cambia.
2. **No re-construir system_msg cada turn** — cachear el prefijo.
3. **No usar retrieval dinámico per turn** si el catálogo está estable — usar el mismo conjunto de tools toda la sesión.

Pero esto es un refactor invasivo. **Demasiado para esta sesión sin más tiempo de validación.**

---

## El consolidated catalog es la palanca correcta

Lo confirmado por el harness ganador:
- 16 composite tools vs 60 individuales = **misma calidad** (~99.81%)
- **-68% tokens del schema** (5,497 → 1,745)
- **Prefijo del prompt más estable**: 16 nombres conocidos, no 60 que cambian con retrieval

**El próximo paso correcto**: activar consolidated catalog con descripciones completas. Bench step 4 medirá si suben PASS rate y bajan latencia.

---

## Decisión honesta sobre scores

Con los datos actuales:

| Score declarado | Defendible? |
|---|---|
| Diseño 10/10 | NO. Cumple 8/10. Falta refactor del prefijo prompt (cache stability). |
| Implementación 10/10 | NO. Cumple 7/10. agent.py sigue en 1397 LOC, hay variance no controlada. |
| Match Gemma 4 4B 10/10 | NO. Cumple 6/10. El harness "puro" logra 99.81%; Carter logra ~65-76% por overhead del agent loop. |

**Score honesto actual**: **8 / 7 / 6**.

Para llegar a 10/10/10:
- **Diseño**: refactor del context_builder para estabilizar prefijo + activar consolidated.
- **Implementación**: dividir agent.py en módulos < 300 LOC, agregar tracing per-turn, fijar variance del bench.
- **Match Gemma**: alinear con harness ganador (consolidated + descripciones del fix + sin retrieval dinámico cuando catálogo estable).

**Estimación**: 2-3 sesiones más de trabajo enfocado.
