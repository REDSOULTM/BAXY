# 08 — Hallazgos del repo `Probando Gemma 4`

**Fecha**: 2026-05-11
**Fuente**: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4`

El usuario me pidió analizar este repo porque tiene la investigación previa. Aquí está lo que encontré, sin maquillaje.

---

## 1. Lo que el repo ya validó (con evidencia medida)

### 1.1 Modelo ganador: `gemma-4-E4B-it-Q6_K`

- **Bench Carter 540 medido**: hasta **540/540 (100%)** declarado en `REPORTE_540_GEMMA4.md`.
- **Datos crudos JSON revelan**: `full540_v14 = 539/540 (99.81%)`, `consolidated_v3 = 539/540 (99.81%)`. El "540/540" del reporte es el **reaudit v6** después de calibrar auditor v7.
- **Lectura honesta**: el techo real reproducible es ~**99.8%**, no 100% literal. Sigue siendo excelente.

### 1.2 Iteraciones documentadas v1→v14

| Versión | PASS | Cambio principal |
|---|---|---|
| v1 baseline | 420/540 (77.78%) | system_prompt v3 inicial, server inestable |
| v3 | 503/540 (93.15%) | Auditor terminal_run↔system_gpu equiv, meta-ack matchers |
| v6 | 530/540 (98.15%) | Meta-ack expandido, gui_screenshot↔filesystem |
| v9 | 533/540 (98.70%) | Pip install destructive explícito |
| v11 | 539/540 (99.81%) | stdout/stderr/comillas markers + budget cat 5 |
| v13 | 529/540 (97.96%) | ❌ Strip content + `--reasoning off` regresión |
| **v14** | **539/540** | Auditor markers para "como terminal_run no admite..." |

**Insight**: los saltos grandes (v1→v6) vinieron del **auditor**, no del modelo. El modelo entrega bien; el bench oficial es estricto con strings específicos. Esto explica por qué hoy mi baseline da 75.93%: el auditor de Carter es **más estricto que el del harness**.

### 1.3 Sampling oficial Google (verificado en model card)

```python
T=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0, max_tokens=1280
```

**No bajar T**. Gemma 4 entrenado a T=1.0 con DPO/RLHF. Bajarlo degrada. Carter ya lo usa correctamente.

### 1.4 Decisiones de arquitectura ya tomadas con justificación

| Decisión | Justificación medida |
|---|---|
| Modelo: Q6_K | Comparado contra IQ2_M (91.6%), Q4_K_M (93.3%), Q5_K_M (91.6%), Q8_0 (91.6%). Q6_K = 95% en bench Fase 2 de 60 tests |
| Backend: CUDA, no Vulkan | CUDA 30-40% más rápido en NVIDIA |
| Runtime: llama.cpp, no vLLM | vLLM requiere WSL2+Docker; inviable para usuarios no-técnicos |
| `--reasoning off`: NO | -1.5pp regresión. PR #21418 en b9090 ya maneja thinking |
| Strip content cuando tool_calls: NO | -1.5pp regresión. Build b9090 ya lo hace |
| KV cache: F16, no Q8 | Gemma 4 sensible a KV quant (KL 0.377) |
| mmproj: F16 obligatorio | Q8/Q4 rompe vision/audio |
| Audio nativo: NO reemplaza Whisper | 2/5 en español rioplatense vs Whisper ~95% |

### 1.5 Latencias Alexa-tier (v11 baseline)

| Categoría | p50 | p90 | p99 | Target | Status |
|---|---|---|---|---|---|
| Trivial | 3.81s | 9.02s | 16.64s | <5s | ⚠️ p99 viola |
| Tool simple | 3.53s | 8.56s | 14.78s | <8s | ⚠️ p99 viola |
| App open | 4.91s | 12.97s | 25.06s | <15s | ⚠️ p99 viola |
| Multi-step | 6.84s | 13.97s | 20.64s | <20s | ⚠️ marginal |

**p50 cumple Alexa-tier en todas las categorías.** Los outliers p99 son chains-of-thought largos. **Mitigación documentada: streaming + UI progress bar.**

**Implicación para Carter**: las latencias actuales de Carter (1-tool avg 16s) son **MÁS LENTAS** que el p99 del harness para tool simple (14.78s). Algo en el agent loop de Carter agrega ~2-3s de overhead per turn.

---

## 2. La consolidación 60→16 tools

### 2.1 Datos medidos

| Métrica | 60 individuales | 16 composite | Cambio |
|---|---|---|---|
| Cantidad tools | 60 | 16 | -73% |
| Schema JSON chars | 21,991 | 6,982 | **-68%** |
| Tokens (~) | 5,497 | 1,745 | **-3,752** |
| PASS Carter 540 | ~539/540 | ~539/540 | **idéntico** |

**Misma calidad, -68% tokens.** Esto justifica fuertemente activar consolidated.

### 2.2 Caso crítico C09 Steam — fix de 1 línea

En `consolidated_v1`, **C09 colapsó 0/30** porque el modelo elegía `web_search` o `filesystem` en lugar de `gui_deeplink(steam)`.

**Fix v2 — solo descripción del tool**:
```
"PRIMARIA para apps nativas con URI scheme: steam, spotify, discord, slack...
SIEMPRE preferir esta tool antes que `web` o `filesystem` cuando el usuario menciona estas apps.
Para Steam: 'biblioteca'/'library' (intent=library), ...
NO usar web_search para queries Steam — usar gui_deeplink(steam, search).
NO usar filesystem para chequear si juego está instalado — usar gui_deeplink(steam, library) + gui(screenshot+locate)."
```

**Resultado**: C09 v2 = 30/30 perfecto.

**Lección**: la descripción de tools en schema importa tanto como el modelo. 1 línea bien escrita = 30 cases recuperados.

### 2.3 Carter vs harness — diferencia exacta encontrada

```diff
Carter gui_deeplink (más corto):
"PRIMARIA para apps nativas con URI scheme: steam, spotify... Para Steam: intent
'library'|'store'|'friends'|'downloads'|'search'(params.query)|... NO usar
web_search para queries Steam → usar gui_deeplink(steam,search)."

Harness ganador (3 frases más):
+ "SIEMPRE preferir esta tool antes que `web` o `filesystem` cuando el usuario menciona estas apps."
+ "Para Steam: 'biblioteca'/'library' (intent=library), 'tienda'/'store' (intent=store),
   'busca X'/'search' (intent=search, params={query:X})."
+ "NO usar filesystem para chequear si juego está instalado — usar gui_deeplink(steam, library)
   + gui(screenshot+locate)."
```

Carter tiene una versión **incompleta** del fix. Es 1 línea más corta y le falta el redirect explícito de `filesystem` para Steam queries.

---

## 3. Por qué Carter tiene 75.93% y el harness tiene ~99.81%

### 3.1 No es el modelo

Mismo modelo Q6_K, mismo llama-server, mismo sampling. La diferencia tiene que estar en lo que rodea al modelo.

### 3.2 Hipótesis ranking (orden por probabilidad)

1. **Auditor estricto en Carter**: el bench oficial de Carter mide cosas que el harness del repo no mide (tools llamadas en orden esperado, latencia con budgets ajustados, etc.). El harness usa stubs deterministas y auditor más laxo.

2. **Catalog individual (60 tools) por default**: en Carter está `individual`, no `consolidated`. El modelo ve 60 tools (top-K reduce a ~25 visibles con anchors). El harness en consolidated mostró que 16 tools = misma calidad pero el modelo decide más rápido.

3. **Overhead del agent loop**: Carter tiene retrieval + step_planner + mission_detector + heurísticas post-LLM. El harness es **prompt + tools + LLM**, nada más. Cada turn extra agrega 2-5s.

4. **Descripciones de tools incompletas**: el ejemplo de `gui_deeplink` muestra que Carter quitó frases críticas del fix v2 del harness.

5. **Latencia budgets de Carter más estrictos**: el bench oficial castiga >15s en C06, >30s en C14. El harness no mide latencia con budget hard.

### 3.3 Lo que SÍ podemos copiar del harness

| Cambio | Costo | Impacto esperado |
|---|---|---|
| Restaurar descripciones completas en `schemas_consolidated.json` | 5 min | +5-15 pts si activamos consolidated |
| Activar `CARTER_TOOL_CATALOG=consolidated` por default | env var | -3,752 tokens, latencia probable -10-20% |
| Verificar que Carter usa `max_tokens=1280` (no 768) | 5 min | Evita finish_reason=length |
| Confirmar `--reasoning off` NO está activo | 5 min | Evita -1.5pp regresión |
| Confirmar build llama.cpp b9090+ | curl /version | PR #21418 necesario |

---

## 4. Plan revisado de mejora — basado en evidencia del repo

### Paso A (próximo): activar consolidated catalog

1. Copiar el `tool_schemas_consolidated.json` del harness ganador (con descripciones completas) a `Carter_v4/src/carter_v4/tools/schemas_consolidated.json`.
2. Setear `CARTER_TOOL_CATALOG=consolidated` por default en `AgentConfig.from_gemma()` o env.
3. Bench oficial 54 P0 + 540 full.

### Paso B: medir si la latencia baja

Si paso A da PASS rate similar o mejor + latencia -20% → activar consolidated default.

### Paso C: investigar overhead de agent loop

Si paso A todavía da peor latencia que el harness, el problema es agent loop overhead:
- retrieval (multilingual-e5-small encode per turn): ~30-50ms cada uno
- step_planner + mission_detector: ~10-20ms
- post-LLM heurísticas: ~10-30ms
- _compute_post_action_steps inyección extra: 1 tool dispatch extra (~6s)

Sumados: 50-100ms en código + posibles tools extras = 6-7s. Eso explica el delta.

---

## 5. Implicación sobre los scores 10/10/10

### Diseño arquitectónico
El **harness** prueba que con prompt + tools + LLM se llega a ~99.8%. Carter v4 implementa toda una capa de "infraestructura inteligente" (retrieval, planner, mission_goal, loop detection, etc.) que **agrega valor para usabilidad real** (multi-turn, contexto, follow-ups, memoria) pero **agrega overhead que el bench castiga**.

El score arquitectónico no debe medirse solo contra el bench. Hay que medir **fidelidad a los 30 valores Carter**:
- V16 (misiones compuestas): Carter > harness, porque tiene contexto multi-turn
- V14 (memoria): Carter > harness, porque tiene SQLite
- V17 (transparencia progreso): Carter > harness, porque tiene streaming
- V24 (pruebas reales): Carter < harness, porque el bench está más estricto

### Implementación
El harness es **monolítico** (un solo proceso, sin retrieval). Carter es **modular**. Modular es mejor para mantener pero peor para latencia.

### Match con Gemma 4 4B
**Aquí el harness gana claramente**: usa el modelo "puro" + un prompt iterado 14 veces. Carter le agrega 4 routers + retrieval + heurísticas. Si vamos a maximizar match con Gemma 4 4B, hay que **acercar Carter al setup del harness**.

---

## 6. Decisión basada en este análisis

**El plan correcto NO es perseguir 540/540 en el bench de Carter** copiando todo el harness. Es:

1. **Activar consolidated catalog** (paso A) con descripciones completas. Probable +5-15 pts inmediato.
2. **Medir si activando consolidated, el agent loop sigue agregando overhead**. Si sí, optimizar (paso C).
3. **Aceptar honestamente** que Carter v4 con todas sus capas pierde 2-5 pts vs el harness "puro", a cambio de funcionalidad real (memoria, follow-ups, streaming, verificación post-acción).

El **score honesto** que defendería:

| Dimensión | Carter v4 actual | Carter v4 + consolidated | Harness puro |
|---|---|---|---|
| Bench PASS rate | 75.93% | ~85-95% (estimado) | ~99.81% |
| Funcionalidad real (multi-turn, memoria) | 10/10 | 10/10 | 5/10 |
| Latencia | 6/10 | 7-8/10 | 9/10 |
| Mantenibilidad | 6/10 (agent.py 1397 LOC) | 7/10 | 8/10 |

**Score defendible para Carter v4 + consolidated activado**: ~8.5/10 (diseño), ~7.5/10 (impl), ~8/10 (match Gemma).

**Para 10/10/10 real**: necesitamos un nivel adicional de refactor que en este momento no está validado contra el bench. Lo correcto es **declarar el score actual + plan claro de qué falta**, no inflar.

---

## 7. Próximas acciones

1. Esperar bench paso 1 (revert prompt + anchors) — sabrá si MissionGoal + eager rompen algo.
2. Copiar descripciones completas del `tool_schemas_consolidated.json` del harness.
3. Activar consolidated y medir bench oficial.
4. Si consolidated mejora PASS rate Y latencia → declarar como default.
5. Documentar score honesto final.
