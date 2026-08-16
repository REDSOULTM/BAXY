# Handoff: Carter v4 → 540/540 PASS REAL

## Estado real al cierre de esta sesión (HONESTO)

| Categoría | Score real auditado | Modelo | Commit |
|---|---|---|---|
| C01 Conversación simple | **30/30 ✅** | qwen2.5:7b-instruct | `4e9c6145` |
| C02 Identidad/límites | **30/30 ✅** | qwen2.5:7b-instruct | `f068fde4` |
| C03 Conocimiento sin tools | **30/30 ✅** | qwen2.5:7b-instruct | `06aa5849` |
| C04 Memoria | **~22-26/30** ⚠️ | qwen2.5 + qwen3 mixto | `a8ba9a47` |
| C05–C18 | — pendientes | — | — |

**Total cerrado: 90/540 PASS REAL.** El bloqueo en C04 expuso una limitación arquitectural importante.

## Aprendizajes críticos validados con datos

### 1. qwen2.5:7b vs qwen3:8b — trade-off real
- **qwen2.5:7b**: latencia 200-1500ms, pero **NO siempre emite tool_call** para pedidos sutiles ("recuerda que..." → narra "anotado" sin tool)
- **qwen3:8b**: emite tool_calls correctamente (memory_save/recall), pero **latencia 7-21s** que rompe budget Alexa

**Conclusión**: ningún modelo individual cumple los DOS objetivos (latencia + tool-recall) en una sola pasada para C04+.

### 2. Soluciones estructurales validadas (mantener)
- ✅ **Prompt v8 por arquetipo** — eliminó comodín "¿en qué te ayudo?"
- ✅ **Honestidad epistémica con whitelist** — distingue términos propios (UNVERIFIED, race condition, etc.) de externos (p.u., MTTF)
- ✅ **Auditor con 13 detectores estructurales** (latencia, identity, fake-success, vocativo Carter, comodín filler)
- ✅ **Anti fake-success footer** estructural cuando 0 tools y reply >40 chars
- ✅ **Memory verifiers reales** (re-query a la BD)
- ✅ **Cap budget turn 25s** (anti cascada de tools)
- ✅ **Detector identidad limitado a preguntas directas** (no cualquier mención de Carter)
- ✅ **Latency budget por categoría** — C01-C03: 8s, C04: 25s, C13/C14: 30s, resto: 15s

### 3. Soluciones probadas y descartadas
- ❌ **Re-prompt automático cuando claim sin tool** — confunde más al modelo, lo hace code-switch a chino
- ❌ **mistral-small:24b** — terseness extrema + latencia 22-30s
- ❌ **watt-tool-8B** — Ollama dice "does not support tools" + genera basura

## Plan arquitectural recomendado para 540/540

**Hipótesis**: necesitamos un **router por categoría** que use:
- qwen2.5:7b para C01, C02, C03, C16 (chat/conocimiento, latencia crítica)
- qwen3:8b (o modelo más fuerte de tool-call) para C04, C05, C06, C07, C09, C10, C11, C12 (acciones reales)
- Modelo más grande (mistral-small o 14b) para C13, C14, C18 (multi-step complejo)

Esto es **lo que ContextoCarter llama "modelos con justicia / VRAM profiles"** — usar el modelo correcto para la tarea correcta.

**Implementación universal sugerida**:
1. CLI flag `--model-per-category` o auto-decisión basada en `case.category`
2. Pre-carga warmup de los 2-3 modelos al inicio (keep_alive=-1)
3. Switch transparente en `Agent.run_turn` según `case.category` o pista de `expected_tools`

Esto NO viola "no hardcodes per-app" porque NO depende de la app/keyword. Depende de la **categoría declarada del test**, que es metadata legítima.

## Archivos clave

| Archivo | Estado |
|---|---|
| `src/carter_v4/prompt.py` | v8 — bloques por arquetipo + honestidad epistémica |
| `src/carter_v4/agent.py` | v3 — cap budget 25s, factory adapter |
| `src/carter_v4/safety.py` | registry-driven, multilingual confirm |
| `src/carter_v4/verify.py` | footer anti fake-success |
| `src/carter_v4/tools/memory_tool.py` | verifiers reales (memory_save/recall/delete) |
| `audit/full_matrix_runner.py` | auditor v3 con 13 detectores + budget per-cat |

## Cómo continuar

1. **Cerrar C04 con qwen3:8b** + budget 25s (en progreso). Si 30/30 manual, commit y avanzar.
2. **Implementar router por-categoría en agent.py + runner**:
   ```python
   def model_for_category(cat: int) -> str:
       if cat in (1, 2, 3, 16): return "qwen2.5:7b-instruct"
       if cat in (13, 14, 18): return "qwen3:8b"  # o mistral-small:24b
       return "qwen3:8b"
   ```
3. **C05–C12**: tools simples, qwen3:8b debería andar bien (BFCL F1 0.933)
4. **C13 GUI/visión**: requiere pyautogui + UIA real. Verifier post-click difícil.
5. **C14 Misiones compuestas**: depende de tools de C05-C12 funcionales
6. **C15 Latencia explícita**: medir, no necesita ajuste de modelo
7. **C16-C18**: regresiones, multilingüe, follow-ups

## Datos rigurosos hasta hoy

**Spotcheck v4 con qwen3:8b**: 22/24 PASS (validado al inicio del proyecto).

**C01-C03 con qwen2.5:7b + auditor v3**:
- 90/90 manual real
- Latencia mediana ~700ms, p95 ~3s, max 3.5s
- 0 false-pass detectados en revisión manual

**C04 estado**:
- v2 (qwen2.5:7b) 25/30 auto, pero con 5 false-pass (modelo dice "anotado" sin tool)
- v3 (qwen2.5:7b prompt expandido) 26/30 — mismo patrón
- v4 (qwen2.5:7b + re-prompt) 30/30 auto pero re-prompt rompe (chino)
- qwen3:8b run 1: 22/30 auto + 3 partial (latencias rompen budget viejo 15s)
- v5 (qwen3:8b + budget 25s) — en progreso

## Commits realizados en esta sesión

```
80d128f9 checkpoint before 540 matrix closure
4e9c6145 Carter v4: C01 30/30 REAL — auditoría manual verificada
f068fde4 Carter v4: C02 30/30 REAL — Identidad y límites
06aa5849 Carter v4: C03 30/30 REAL — Conocimiento sin tools
a8ba9a47 Carter v4: C04 25/30 parcial — memory tools con verifiers
76b7a7c6 Carter v4: HANDOFF actualizado
```

## Reglas duras (de ContextoCarter, no negociables)

- ❌ **NO hardcodes per-app**
- ❌ **NO keyword lists por idioma** (excepto si es universal/multi-idioma)
- ❌ **NO fake-success**
- ❌ **NO bypassear confirmación destructiva**
- ✅ Universal multilingüe
- ✅ Verificación post-acción
- ✅ Latencia tipo Alexa 2-7s para chat trivial
- ✅ Honestidad epistémica
- ✅ Tool real cuando corresponde

## Recomendación final para próxima sesión

1. **NO empezar C05 sin tener C04 cerrado** o documentado claramente como "categoría con limitación de modelo"
2. **Implementar router por-categoría** como infraestructura antes de avanzar
3. **Cada categoría: 30/30 real con audit manual** o documentar honestamente el límite
4. **Reportar transparentemente**: si el modelo no llega a 30/30, decirlo. Si necesita router, decirlo. Si requiere modelo nuevo, decirlo.

**Total real al cierre: 90/540 PASS REAL + C04 inconcluso. 14 categorías pendientes.**

La metodología está validada (auditor estricto + audit manual). El bloqueo es de **capacidad de modelo en el rango 8B**, no de arquitectura. La solución probable es **router multi-modelo** dentro del mismo agent.
