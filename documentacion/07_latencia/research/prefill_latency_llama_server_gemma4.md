# Informe técnico: minimizar latencia de PREFILL en Gemma 4 E4B-it Q4_K_M sobre llama-server (build b9090+)

## TL;DR

- **El cuello de botella es la inestabilidad del prefijo del system prompt, no el modelo ni el flag de cache.** En tu medición, el "tail" reprocesado mediano (~3906 tokens) coincide casi exactamente con el bloque variable que el router de subset inserta tras un common prefix estable de ~900 tokens. La mayor ganancia (estimada **−700 a −2200 ms p50/p90 de prefill, ≥85% cache-hit**) viene de **mover todas las definiciones de herramientas a un prefijo estable** y dejar la señalización del subset al final (en el último mensaje), no de tocar más flags.
- **En llama-server build b9090+ la configuración correcta para Gemma 4 (iSWA) es `-fa on --swa-full` y opcionalmente `--cache-reuse 256`**, porque (a) PR #22288 (autor: ggerganov; supersedea PR #21749 cerrada el 29-abr-2026) arregló justamente el caso de Gemma 4 + `--swa-full` que reprocesaba todo en cada turno, y (b) `--cache-reuse` es —en palabras del propio ggerganov en Discussion #22354— *"misleadingly named […] a processing trick to allow you to keep the tail end of prefilled sequence after deleting earlier parts"*, lo que puede degradar tool-calling. `--ctx-checkpoints` deja de tener efecto cuando `--swa-full` está activo (la PR #22288 explícitamente *"skips checkpoint restoration logic when swa_full is enabled"*).
- **Speculative decoding NO aplica** en tu caso (generación ya cuesta 386 ms, y un draft model E2B-it Q4_K_M de 3.11 GB sobre E4B-it Q4_K_M de 5.34 GB suma 8.45 GB, excediendo 6 GB de VRAM). **GBNF/grammar constrained** sí mejora robustez de tool-calling pero su efecto en TTFT es marginal. **Cambiar de runtime (vLLM/SGLang) no aplica**: la documentación oficial de vLLM advierte textualmente que *"GGUF support in vLLM is highly experimental and under-optimized at the moment, it might be incompatible with other features"*, y el RFC vLLM #39583 propone incluso deprecar GGUF.

---

## Hallazgos clave

### Mapa del problema (lectura de tus medidas)

| Métrica medida | Valor (mediana) | Diagnóstico |
|---|---|---|
| Total per-turn | 2054 ms | OK p50, pero p90 catastrófico (>10 s) |
| Prefill | 3906 tok @ 4400 tok/s ≈ 888 ms | **bottleneck principal** |
| Generation | 21 tok @ 62 tok/s ≈ 386 ms | OK |
| Total prompt | 7875 tok | acumula historia |
| Cache reuse efectivo | ~6144 tok | dependiente del prefijo común |
| Prefijo común entre subsets | ~3659 chars / ~900 tokens | **causa raíz** |

Tu log `memory_seq_rm [4, end)` confirma que el matching del prefix-cache es por LCP (Longest Common Prefix) y se rompe en el primer carácter divergente. Esto coincide con el tutorial oficial de KV cache reuse de llama.cpp (Discussion #13606): *"the current slot selection logic picks a sufficient match based on LCP similarity"*. Una vez que la usage-rule o el schema-hint del primer tool del subset cambia, todo lo posterior se recomputa.

### Estado actual del soporte SWA / cache para Gemma 4 en llama.cpp (importante)

- **Gemma 4 E4B usa iSWA con n_swa = 1024**, confirmado verbatim en la descripción de la PR #22288 de ggerganov: *"pos_min_thold = pos_next - n_swa, which for Gemma 4 means pos_next - 1024."* La estructura de capas es 5× sliding + 1× full, repetida 10 veces → 50 capas SWA + 10 globales (documentado en ik_llama.cpp issue #1607). En tu config tienes `--swa-full -ngl 99 -c 16384`, lo cual asigna cache SWA full-size (sin pruning) — correcto para reuse máximo.
- **PR #21749 ("server: ensure prompt caching for SWA models", autor: usuario `shipped-it`, NO ggerganov)** fue **cerrada sin merge el 29-abr-2026**, *"superseded by #22288"*. La PR #22288 ("server : fix swa-full logic", autor ggerganov) fue mergeada (~23-abr-2026) e implementa el mismo fix descrito en #21749: *"Setting pos_min_thold = 0 when swa_full is enabled (any cached position is useful)"* y *"Skipping checkpoint restoration logic when swa_full is enabled (unnecessary since cache is full-size)"*. El issue de origen #21468 fue abierto el 5-abr-2026 sobre build b8660 (commit d006858) afectando explícitamente `ggml-org/gemma-4-E2B-it-GGUF` y `ggml-org/gemma-4-E4B-it-GGUF`.
- **Build b9090+ debería contener PR #22288.** Con `--swa-full` el path *"forcing full prompt re-processing due to lack of cache data"* para Gemma 4 ya no debería dispararse, y la reutilización por LCP es la vía principal. *Caveat*: si tu logging aún muestra "cache reuse is not supported - ignoring n_cache_reuse = 256", verifica `llama-server --version` y bumpea el build.
- **`--cache-reuse` opera por KV shifting, no por LCP simple.** Cita textual de ggerganov en Discussion #22354: *"--cache-reuse is misleadingly named. It's a processing trick to allow you to keep the tail end of prefilled sequence after deleting earlier parts, but crucially while pretending that the earlier parts are still there."* Esto es peligroso para tool-calling: deja "trazas" del prefijo viejo en el contexto.
- **`--ctx-checkpoints` y `--checkpoint-every-n-tokens` son DE FACTO INOPERANTES con `--swa-full`.** La descripción de PR #15293 (ggerganov) es explícita: *"Checkpoints are created only if the --swa-full argument is not specified. If the argument is used, we can branch from any past positions of the context (so no need to do checkpoints), but the drawback is that the SWA memory size is much larger in this case."* La PR #22288 confirma: *"Skipping checkpoint restoration logic when swa_full is enabled (unnecessary since cache is full-size)."*

**Implicancia inmediata para tus flags actuales** `--ctx-checkpoints 1 --cache-reuse 256 --swa-full`:
- `--ctx-checkpoints 1` es ruido (no se usa con `--swa-full`).
- `--cache-reuse 256` está activo pero puede no estar haciendo lo que crees. En Gemma 4 + `--swa-full` post-#22288, el reuse "limpio" por LCP ya está garantizado; el extra de cache-reuse vía shifting es opcional y arriesgado para tool-calling. Recomendación: **mantener `--cache-reuse 256`** sólo si verificás (vía `timings.cache_n`) que aporta tokens extra reusados; si no, **quitarlo**.

---

## Punto 1 — ESTRATEGIA DE LAYOUT DE PROMPT (máxima prioridad)

### Diagnóstico

El prefix-cache de llama.cpp matchea por **LCP de tokens, no por similitud semántica**. Cualquier byte que cambie en posición `i` invalida todo desde `i` hasta el final. Como tu `build_system_prompt(selected_tool_names)` y `_tool_schemas_hint(selected_tool_names)` cambian con el subset, el prefijo estable colapsa a ~900 tokens (el "core" antes de las usage rules).

### Tres caminos evaluables

**Camino A — Optimizar DENTRO del router de subset (prefijo estable + variable al final)**

Refactorización mínima:
```
SYSTEM = [
  CORE_INSTRUCTIONS,              # fijo, ~500-800 tok
  ALL_TOOL_USAGE_RULES_COMPACT,   # fijo, todos los tools en formato compacto, ~1500-2500 tok
  ALL_TOOL_SCHEMAS_HINT,          # fijo, "Tool Schemas EXACT" para todos, ~6000-9000 tok
]
LAST_USER_MSG_PREFIX = "[ROUTER HINT: prioriza estos tools en este turno: tool_a, tool_b]\n" + user_msg
tools = [todos_los_65_tools]      # OpenAI param: estable
```

Lo crítico: **el subset NO va en system; va como prefijo del último user msg**. Eso preserva el prefix-cache para system + tools + historia previa.

**Camino B — Stable prompt completo (todos los 65 tools)**

Lo mismo que A pero confiando en que el modelo (con `tools=[ALL]`) decida solo. Riesgo conocido por el usuario: E4B-Q4 con 65 tools en contexto alucina argumentos. **Descartar** salvo que se acompañe con grammar (ver Punto 4).

**Camino C — Middle ground: core-set fijo + extras al final**

```
SYSTEM = [
  CORE_INSTRUCTIONS,                                      # ~500-800 tok
  CORE_15_TOOLS_USAGE_RULES + CORE_15_SCHEMAS,            # fijo, ~3000-4000 tok
]
LAST_USER_MSG_PREFIX = (
  "[EXTRA TOOLS for this turn (use only if needed):\n"
  + serialize_subset_minus_core(selected_tool_names)      # variable, ~500-1500 tok
  + "]\n" + user_msg
)
tools = core_15 ∪ selected_subset                         # OpenAI param: parte estable + variable
```

### Aritmética concreta (estimaciones, no medidas — verifícalas con tu hardware)

Asumimos prefill efectivo de **4400 tok/s** (tu medida) y ratio chars→tokens ≈ 3.5 para tu prompt (medido: 42383 chars ≈ 10-12K tokens implica ratio ~3.7).

| Camino | System tokens estables | Tail variable por turno | Cache-hit % | Prefill p50 (ms) | Prefill p90 (ms) | ctx libre para historia (de 16384) |
|---|---|---|---|---|---|---|
| **Actual** (subset en system) | ~900 | ~3900 + historia | ~22% | **888** (medido) | **2554** (medido) | ~8500 tok (≈16384−7875) |
| **A — stable prefix + ALL schemas** | ~10500 | <100 (hint en user) + delta historia | **≥95%** del system | **~50 ms** (sólo último user+delta) | **~150 ms** | **~5800 tok** — apretado |
| **B — descartar router** | ~10500 | delta historia | ≥95% | ~50 ms | ~150 ms | ~5800 tok |
| **C — core 15 + extras al final** | ~3500-4500 | ~500-1500 + delta historia | **~70-85%** | **~150-300 ms** | **~500-800 ms** | **~10500 tok** — cómodo |

> **Notas de honestidad**: estos números son cotas calculadas sobre tu throughput de prefill medido, asumiendo cache-hit completo del system. NO son medidas. Hay que validar con `timings.cache_n / timings.prompt_n` en la respuesta (campo expuesto por llama-server, ver más abajo).

### Verdicto para TU stack

> **Camino C (middle ground) es el ganador en net latency sin degradar tool-calling.**

Razonamiento:
1. Camino A te deja ~5800 tokens de historia útil con 16384 de contexto. Con tu crecimiento medido de ~3900 tok/turno acumulado, se llena en 1–2 turnos largos. **Marginal y frágil**.
2. Camino B repite el problema de hallucination que ya tuviste con 65 tools.
3. Camino C **estabiliza el prefijo en ~4000 tokens** (cubre ~70–85% del prompt típico), preserva espacio para historia (~10500 tok), y mantiene tool-calling acotado (15 tools fijos + ≤6 extras señalados al final).

**Criterio de selección de los 15 tools core**: por log de uso (Pareto). Si tu router ya tiene métricas, ordena por frecuencia de selección por turno (cobertura ≥85% con N≤15 es típica).

### Plantilla Python ready-to-paste

```python
# build_prompt.py — Camino C
CORE_TOOLS = frozenset([
    # los 10-15 más usados (sacarlos del log de tu router)
    "whatsapp_send", "whatsapp_read", "contacts_lookup",
    "office_search", "filesystem_read", "filesystem_write",
    "calendar_event", "weather_now", "web_search", "memory_save",
    "memory_recall", "music_play", "timer_set", "smart_home_toggle", "noop",
])

def build_stable_system_prompt(all_tool_specs: dict) -> str:
    """Genera el prefijo ESTABLE (mismo bytes turno-tras-turno)."""
    parts = [CORE_INSTRUCTIONS_TEXT]
    parts.append("\n## Tool usage rules (always available)\n")
    for name in sorted(CORE_TOOLS):  # sorted() => orden determinista
        parts.append(all_tool_specs[name]["usage_rule"])
    parts.append("\n## Tool schemas (exact, JSON-conformant)\n")
    for name in sorted(CORE_TOOLS):
        parts.append("```json\n" + all_tool_specs[name]["schema_json"] + "\n```\n")
    return "".join(parts)

# Pre-computar UNA VEZ al arrancar el servicio
STABLE_SYSTEM = build_stable_system_prompt(ALL_TOOL_SPECS)

def build_request(user_msg: str, selected_extras: list[str], history: list[dict]):
    extras = [t for t in selected_extras if t not in CORE_TOOLS]
    if extras:
        extras_block = (
            "[ROUTER HINT: tools adicionales útiles para esta consulta "
            "(úsalos sólo si CORE no alcanza):\n"
            + "\n".join(
                f"- {n}: {ALL_TOOL_SPECS[n]['short_desc']}\n"
                f"  schema: {ALL_TOOL_SPECS[n]['schema_json']}"
                for n in extras
            )
            + "]\n\n"
        )
    else:
        extras_block = ""

    return {
        "model": "gemma-4-E4B-it",
        "messages": (
            [{"role": "system", "content": STABLE_SYSTEM}]
            + history
            + [{"role": "user", "content": extras_block + user_msg}]
        ),
        # tools=[...] = unión core + extras, en ORDEN DETERMINISTA
        "tools": [
            ALL_TOOL_SPECS[n]["openai_tool_def"]
            for n in sorted(CORE_TOOLS | set(extras))
        ],
        "cache_prompt": True,   # default true, pero explicitarlo
        "temperature": 0.1,
    }
```

**Anti-patrones críticos** (cualquiera de éstos rompe el cache turno-tras-turno):
- `datetime.now()` o IDs aleatorios en el system prompt.
- Orden no determinista de tools/usage rules (usa `sorted()`).
- Concatenación de strings con espacios variables (normaliza whitespace).
- Re-renderizar el system prompt en cada request en vez de cachear el string.

### Cómo medir si efectivamente está funcionando

llama-server (b9090+) devuelve en cada respuesta un objeto `timings` con dos campos clave (verificado en el README oficial del server `tools/server/README.md`):

```python
# Ejemplo de campos retornados:
# "timings": {
#   "cache_n": 236,         # tokens reusados del cache (system + historia)
#   "prompt_n": 1,          # tokens reprocesados (sólo el delta)
#   "prompt_ms": 30.958,
#   ...
# }
# Cita verbatim de la doc: "cache_n: number of prompt tokens reused from cache"
```

Tu meta debería ser `cache_n ≈ len(system_tokens) + len(history_tokens_anteriores)` y `prompt_n ≈ len(last_user_msg_tokens) + len(extras_block_tokens)`. Si `prompt_n` >> `len(last_user_msg)`, el prefijo se está rompiendo en otra parte (típicamente: jinja inserta los tools en orden distinto, o tu historia normaliza el campo `tool_calls` de un turno previo de forma diferente — *verifica esto explícitamente*).

---

## Punto 2 — Squeezing de --cache-reuse y prefix-cache en SWA (alta prioridad)

### Cómo funciona realmente el matching en llama.cpp

1. **Selección de slot** (`server_context::get_available_slot`): por **LCP similarity** con threshold `--slot-prompt-similarity / -sps` (default 0.10). Con `--parallel 1` esto se simplifica a "siempre el mismo slot".
2. **Determinación del prefix reusable** dentro del slot: tokens cacheados que coincidan byte-a-byte con el inicio del nuevo prompt. La traza típica es `slot.prompt.tokens.size() = N, n_past = K` con `K` = tokens reusados.
3. **Camino sin `--swa-full`**: `pos_min_thold = pos_next - n_swa` (para Gemma 4: `pos_next - 1024`, verbatim en PR #22288). Si la posición mínima cacheada no cae bajo el threshold, se intenta restaurar desde un **context-checkpoint** (PR #15293, #19408).
4. **Camino con `--swa-full`** (a partir del fix #22288): `pos_min_thold = 0` y la restauración de checkpoints se omite. **Cualquier posición cacheada sirve.** Este es el camino *correcto* para Gemma 4 en una conversación creciente.
5. **`--cache-reuse N`** (`n_cache_reuse`): la doc verbatim del server README dice *"Min chunk size to attempt reusing from the cache via KV shifting. For more info, see --cache-reuse arg. Default: 0, which is disabled."* Opera *después* del LCP, intentando reusar bloques de tamaño ≥N en el medio del prompt mediante KV-shifting. Para conversaciones donde la historia crece *al final* (tu caso), el LCP solo basta; cache-reuse aporta solo si insertás/borrás cosas en el medio.

### Qué INVALIDA el matching (lista exhaustiva práctica)

| Invalida | Explicación / mitigación |
|---|---|
| Cualquier cambio de bytes en el system prompt | Mantener `STABLE_SYSTEM` precomputado |
| Reordenar `tools=[...]` | Ordenar `sorted()` siempre |
| Cambiar el chat template (`--jinja` aplica al render) | No cambiar `--chat-template-file` en runtime |
| Reescribir `tool_calls` de turnos previos al recomponer historia | Persistir el render exacto que envió el server |
| Cambiar `--seed`, `--temperature` no invalida cache (afecta solo sampling) | OK |
| `--parallel >1` con LRU eviction | En `--parallel 1` no hay riesgo |
| Build entre b8825–b8891 | Bug histórico (#15082). Confirma que estás en b9090+ |
| Build entre b8660–b8920 con Gemma 4 y `--swa-full` | Bug #21468 resuelto por PR #22288. b9090 lo incluye. |

### Tabla comparativa de opciones

| Configuración | Prefill p50 esperado | Cache-hit | VRAM extra (SWA) | Riesgo tool-calling | Notas |
|---|---|---|---|---|---|
| `--swa-full` (sin cache-reuse) **[recomendado]** | ~50–300 ms (con layout C) | LCP completo | +SWA full (~+250 MB en 16K) | Bajo | Camino limpio post-#22288 |
| `--swa-full --cache-reuse 256` | igual o ligeramente menor | + cache shifting | igual | Medio (trazas) | Sólo si `timings.cache_n` muestra ganancia real |
| sin `--swa-full`, con `--ctx-checkpoints 32 --checkpoint-every-n-tokens 2048` | ~200–800 ms | Sólo cerca del checkpoint | −SWA savings | Bajo | Útil sólo si VRAM es el bottleneck |
| Sin nada | full reprocess en cada turno | 0% en SWA | Mínimo | Bajo | Inviable |

### Verdicto

> **Mantener `--swa-full -fa on` y quitar `--ctx-checkpoints 1` (no hace nada con swa-full).** Probar A/B con y sin `--cache-reuse 256` midiendo `timings.cache_n` y `timings.prompt_n` en >100 turnos cada uno; conservar la que dé mayor `cache_n / (cache_n + prompt_n)` medio.

### Flags recomendados finales

```bash
llama-server \
  --model gemma-4-E4B-it-Q4_K_M.gguf \
  -c 16384 \
  -ngl 99 \
  --parallel 1 \
  --jinja \
  --flash-attn on \
  --swa-full \
  --keep -1 \
  --no-context-shift \
  --cache-reuse 256 \
  # quitado: --ctx-checkpoints 1   (inoperante con --swa-full)
  --slot-prompt-similarity 0.0     # forzar siempre slot 0 (con --parallel 1)
```

`--no-context-shift` (default disabled desde la consolidación post-PR #15416, citado en server README: *"whether to use context shift on infinite text generation (default: disabled)"*) evita el shifting rotacional implícito que **rompe el prefix-cache** cuando el contexto se llena. Si excedés el ctx, mejor fallar explícito y compactar la historia desde el cliente.

---

## Punto 3 — Speculative decoding

### Diagnóstico

Tu generación es **386 ms por 21 tokens**. Speculative decoding atiende generación, no prefill. ROI máximo posible (asumiendo 2× speedup como con MTP en Qwen 3.6, según braincuber.com benchmark RTX 3090): bajar 386 → ~200 ms. Eso es **~186 ms** ganados en un budget per-turn donde el problema es el p90 de prefill (>2500 ms).

### Análisis de viabilidad en 6 GB

- llama.cpp soporta draft models vía `--spec-draft-model / -md`, `--spec-type draft-simple / draft-eagle3 / draft-mtp / ngram-simple / ngram-map-k / ngram-map-k4v / ngram-mod / ngram-cache`. Docs: `docs/speculative.md`.
- Requisitos: draft y target deben **compartir vocab** (*"llama_vocab_type must match"*, *"BOS and EOS token IDs and 'add BOS/EOS' flags must be identical"*, según `common/speculative.cpp:49-77`). Gemma 4 E2B-it sería candidato natural como draft para E4B-it (mismo tokenizer Gemma).
- **VRAM bloqueada**: E2B-it Q4_K_M pesa **3.11 GB** (según `unsloth/gemma-4-E2B-it-GGUF` en Hugging Face, SHA256 9378bc47…). E4B-it Q4_K_M pesa **5.34 GB** (`ggml-org/gemma-4-E4B-it-GGUF` lista textualmente "4-bit · Q4_K_M · 5.34 GB"; la versión de unsloth muestra 4.98 GB). Combinados son **8.09–8.45 GB**, muy por encima de tus 6 GB **incluso sin overhead de KV cache**.
- Tendrías que offload el draft a CPU (`--device-draft CPU` o `--n-cpu-moe-draft`), lo que **anula el speedup** porque el draft se vuelve más lento que la verificación.
- Alternativa: speculative *self*-speculative (`--spec-type ngram-mod` o `ngram-simple`). No requiere modelo extra, busca patrones n-gram en el historial. **Funciona bien en código repetitivo, mal en voz conversacional** (poca repetición).

### Verdicto

> **No aplicar speculative decoding.** ROI < 200 ms en escenario optimista, costo VRAM bloquea draft model GPU (8.45 GB no entra en 6), y el caso de voz no se beneficia de self-speculative. **Descartar.**

Si tuvieras 8 GB+ de VRAM y la latencia de prefill ya estuviera resuelta, valdría considerar `--spec-type draft-simple -md gemma-4-E2B-it-Q4_K_M.gguf --spec-draft-n-max 3`. No es tu caso.

---

## Punto 4 — Grammar / GBNF-constrained decoding

### Diagnóstico

GBNF actúa sobre el sampling (durante generación). Su efecto en latencia es:
- **Sobre TTFT**: efecto nulo o ligeramente NEGATIVO (parsing del schema → grammar tiene costo de setup, normalmente <50 ms).
- **Sobre tool-calling reliability en modelos pequeños**: **alto positivo**. Garantiza JSON parseable y nombres de tool válidos.

### Estado en llama.cpp (--jinja interaction)

- **Confirmado** (Discussion #12204, abril 2025): hubo un periodo donde `--jinja` deshabilitaba GBNF. Respuesta del mantenedor: *"Jinja should work w/ grammar (cf. basic test)"*. Está resuelto en builds actuales.
- **Confirmado** (DeepWiki "Chat Templates and Message Parsing"): *"llama.cpp supports complex tool-use patterns by generating GBNF grammars that match the specific format expected by a model's chat template."* El "autoparser" genera GBNF automáticamente desde los `tools=[...]` de OpenAI cuando hay un chat template tool-enabled.
- **Riesgo conocido** (issue #1484 en fork ik_llama.cpp): schemas con `anyOf` complejo, `exclusiveMinimum` o `$schema` pueden crashear el grammar generator (*"The GBNF grammar engine crashes when converting complex JSON Schema constructs (anyOf with multiple types, exclusiveMinimum, nullable unions) into grammar rules"*). Mantén tus schemas simples (sin `oneOf`, sin `anyOf` con múltiples tipos).

### Tabla comparativa

| Modo | TTFT impact | Tool-call reliability E4B-Q4 | Riesgo | Recomendación |
|---|---|---|---|---|
| Sólo `--jinja` (lo que tenés) | baseline | Media (hallucina args con prompts largos) | Bajo | Status quo |
| `--jinja` + `tool_choice: "required"` | baseline | Media-alta | Bajo | Probar |
| `--jinja` + custom GBNF (`grammar` param en request) | +20-50 ms setup | Alta | Medio (schema complejo crashea) | Sólo si Camino C aún alucina |
| `--jinja` + `response_format: {type: "json_schema", json_schema: {...}}` | +20-50 ms setup | Alta | Bajo | **Recomendado** si quieres forzar JSON |

### Verdicto

> **No introduzcas grammar sólo por latencia.** Sí úsalo si tras aplicar Camino C ves hallucination de tool args. La vía limpia es `response_format` con `json_schema` (no `grammar` raw), que se integra mejor con `--jinja` y el parser de tool-calls de llama.cpp.

### Snippet

```python
# Forzar JSON schema en la salida (solo cuando esperas un tool call)
request["response_format"] = {
    "type": "json_schema",
    "json_schema": {
        "name": "tool_call",
        "schema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": list(sorted(CORE_TOOLS | set(extras)))},
                "args": {"type": "object"},
            },
            "required": ["tool", "args"],
            "additionalProperties": False,
        },
    },
}
```

---

## Punto 5 — Reducir el reprocesado de historia

### Diagnóstico

Cada turno suma ~3900 tokens al prompt (user + assistant + tool_results). Con `--swa-full` y prefijo estable el reuse del prefix cubre **todo lo previo cacheado**, así que sólo se reprocesa el **delta** del turno actual (último user msg + el extras_block del router). Tu medida `~3906 tokens reprocesados` confirma que en el régimen actual NO se cachea la historia previa porque cualquier `tool_calls` re-serializado con campos en distinto orden invalida el LCP.

### Técnicas (con su efecto en cache)

| Técnica | Latencia prefill | Cache-safe | Pérdida de contexto | Verdicto |
|---|---|---|---|---|
| **Persistir el render literal de cada turno** (no re-serializar JSON) | −1000 a −2500 ms p90 | ✅ | 0 | **Hacer ya, ROI más alto** |
| Rolling summarization (cada N turnos, resumir los K más viejos) | −500 a −1500 ms si el resumen estabiliza el prefijo | ⚠️ rompe cache una vez por resumen | Pequeña | Útil tras 8–10 turnos |
| Truncar mensajes intermedios manteniendo CORE inicial | Reduce ctx pero rompe cache | ⚠️ | Variable | Sólo si llenas ctx |
| `--context-shift` (rotacional) | Rompe cache, default OFF post-#15416 | ❌ | Estructural | **No usar** |
| Strip de `tool_messages` antiguos (ya lo hacés) | Pequeña ganancia | ⚠️ rompe cache | Mínima | OK, pero no es la palanca |
| Two-tier: cache "active history" + resumir el resto en un bloque que se *concatena al system stable* | Excelente | ✅ si el system se actualiza solo cada N turnos | Mínima | **Recomendado a medio plazo** |

### Patrón "persistencia bit-a-bit del historial"

El error más común: el cliente recompone `messages = [system, *history, user]` pero serializa `tool_calls` con `json.dumps(args, sort_keys=False)` o con espacios diferentes a como lo emitió el server. Solución:

```python
# Cuando el server responde con tool_call, guarda el render TAL CUAL
def append_assistant_turn(history, response):
    # response.choices[0].message es un dict; persistir literal el JSON serializado
    raw = response.choices[0].message
    history.append({
        "role": "assistant",
        "content": raw.get("content"),
        "tool_calls": raw.get("tool_calls"),  # mismo orden de campos que devolvió el server
    })

# Al re-enviar, si tu cliente vuelve a serializar:
import json
def serialize_message_stable(m: dict) -> str:
    # Forzar orden de claves canónico
    return json.dumps(m, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
```

(Esto no afecta cómo llama-server tokeniza el prompt final post-jinja, pero **sí evita** que tu cliente re-renderice diferente turno-a-turno y rompa el prefijo en el campo `tool_calls`.)

### Rolling summarization para conversaciones >10 turnos

```python
SUMMARY_TRIGGER_TURNS = 10
RECENT_TURNS_KEPT = 4

def maybe_summarize(history):
    if len(history) // 2 < SUMMARY_TRIGGER_TURNS:
        return history
    old = history[:-RECENT_TURNS_KEPT * 2]
    recent = history[-RECENT_TURNS_KEPT * 2:]
    summary_text = call_llm_summarize(old)  # llamada barata aparte
    return [
        {"role": "user", "content": f"[CONVERSATION SUMMARY SO FAR: {summary_text}]"},
        {"role": "assistant", "content": "OK, contexto recibido."},
        *recent,
    ]
```

Aceptas que el primer turno post-resumen pague prefill completo, pero los siguientes ~10 turnos vuelven a ser baratos.

### Verdicto

> **Acción inmediata: persistencia bit-a-bit del render de cada turno** (mayor ROI, costo ~0). **Acción a medio plazo: rolling summarization tras 8–10 turnos.** No tocar `--context-shift`.

---

## Punto 6 — ¿Cambiar de runtime?

### Análisis comparativo Gemma 4 E4B en 6 GB de VRAM

| Runtime | Soporte Gemma 4 E4B | Soporte GGUF Q4_K_M | Prefix-caching | VRAM mínimo realista para E4B | Veredicto |
|---|---|---|---|---|---|
| **llama.cpp b9090+** | ✅ nativo (`ggml-org/gemma-4-E4B-it-GGUF`, 5.34 GB Q4_K_M) | ✅ | LCP + checkpoints + cache-reuse | ~5.5–6.5 GB con KV cache 16K | **Stay** |
| **vLLM 0.7+** | ✅ nativo (`google/gemma-4-31B-it` con `--tool-call-parser gemma4`) | Documentación oficial vLLM dice textualmente *"GGUF support in vLLM is highly experimental and under-optimized at the moment, it might be incompatible with other features."* RFC #39583 propone deprecar GGUF (representa ~0.1% del uso pero ~6,000 líneas de kernels CUDA dedicados) | Automatic Prefix Caching (excelente) | E4B con bf16 ~10 GB; con AWQ INT4 ~6 GB **pero AWQ no es GGUF** | **No aplica en 6 GB con GGUF** |
| **SGLang** | ✅ Gemma listado | GGUF en `--load-format gguf` pero docs apuntan a AWQ/GPTQ/FP8 para prefix-cache óptimo | RadixAttention (auto, excelente) | Similar a vLLM | **No aplica** |
| **TGI (HuggingFace)** | ✅ Gemma | GGUF no primario | Cacheado de prefijo básico | Más alto que llama.cpp | No |
| **ik_llama.cpp** | ✅ (fork) | ✅ | TurboQuant KV-cache, cache types granulares por SWA layer (`--cache-type-k-swa`, `--cache-type-v-swa`) | Similar a llama.cpp | Interesante si quieres comprimir KV, pero arrastra bugs de tool-calling (issue #1484). **No para producción de voz.** |

### Veredicto

> **Quédate en llama.cpp.** En 6 GB y con la restricción de GGUF Q4_K_M, vLLM y SGLang no son una opción de "1-clic" — exigen reconvertir el modelo a AWQ/GPTQ o FP8, lo cual cambia tu pipeline y no garantiza paridad de tool-calling con Gemma 4 (los parsers `gemma4` de vLLM existen pero son recientes). **El gap a cerrar no es de runtime, es de layout de prompt y de persistencia de historia.**

Si en el futuro tu VRAM crece a ≥12 GB y aceptas migrar a AWQ INT4, vLLM con `--enable-prefix-caching --enable-chunked-prefill --tool-call-parser gemma4 --reasoning-parser gemma4` daría TTFT por debajo de 100 ms en escenarios similares al tuyo (basado en el codelab oficial de Google Cloud Run con Gemma 4 + vLLM). Antes no.

---

## Recomendaciones (orden de implementación)

### Sprint 1 (hoy, ~2 h de código, ROI más alto)

1. **Refactor a Camino C**: `STABLE_SYSTEM` precomputado con 10–15 tools core fijos + `extras_block` al inicio del último user msg para tools extra del router.
2. **`tools=[...]` ordenado con `sorted()`** (orden canónico determinista).
3. **Persistir el render literal de cada turno** (`tool_calls` con `sort_keys=True` o, mejor, conservar el dict tal-cual lo devolvió el server).
4. **Quitar `--ctx-checkpoints 1`** (inoperante con `--swa-full`); **añadir `--no-context-shift`** y `--slot-prompt-similarity 0.0`.
5. **Instrumentar** `timings.cache_n / timings.prompt_n` en cada respuesta. Meta: `cache_n / (cache_n + prompt_n)` ≥ 0.80 en p50, ≥ 0.60 en p90.

### Sprint 2 (próxima semana)

6. **Bench A/B** con y sin `--cache-reuse 256`. Conservar la que maximice `cache_n` neto sobre ≥200 turnos.
7. **Rolling summarization** a los 10 turnos, conservando los 4 más recientes.
8. **Curar los 15 tools core** con datos reales de tu router (>85% cobertura de invocaciones).

### Sprint 3 (opcional, si aún hay hallucination)

9. Añadir `response_format: {type: "json_schema"}` en tool-call requests.
10. (Sólo si VRAM lo permite) Investigar speculative `ngram-simple` para frases repetitivas del usuario.

### Umbrales que cambian las recomendaciones

| Si observas… | Entonces… |
|---|---|
| `cache_n/prompt_n` < 0.5 en p50 tras Sprint 1 | El prefijo se está rompiendo. Diff bit-a-bit dos requests consecutivos. Causa típica: `datetime` o IDs en system, o `tool_calls` re-serializado distinto. |
| Prefill p90 sigue > 2 s tras Sprints 1+2 | El history kept es demasiado largo. Bajá `RECENT_TURNS_KEPT` a 2. |
| VRAM crece > 5.5 GB con `--swa-full` y OOM | Bajar `-c` a 12288 o probar `--cache-type-k q8_0 --cache-type-v q8_0` (verificar no degrade tool-calling). |
| Tool-calling alucina con Camino C | Activar `response_format` con json_schema (Sprint 3). |
| Migrás a 12+ GB VRAM | Revisitar vLLM con AWQ INT4 y prefix-caching automático. |

---

## Caveats y advertencias de honestidad

- Los números de prefill p50/p90 estimados por camino son **proyecciones** sobre tu throughput medido (4400 tok/s) y la longitud esperada del delta. **Hay que medirlos** con `timings.*` antes de declarar éxito.
- El status de **PR #22288** (merged, ~23–29 abr 2026) lo extraje de cross-references en la PR #21749 cerrada el 29-abr-2026. El commit hash exacto y build number donde aparece no quedó verificado en las fuentes consultadas, así que **verifica `llama-server --version`** y compara con el changelog antes de asumir que el fix está en tu build. La autoría de la PR #22288 es de ggerganov; la PR #21749 (cerrada sin merge) era de un usuario llamado `shipped-it`.
- El issue #21468 muestra estado ambiguo en distintas vistas de GitHub ("Open" en la página directa, "Closed" en algunos snippets vía PR cross-ref). Si tu log muestra todavía `cache reuse is not supported - ignoring n_cache_reuse`, **bumpea el build** antes de cualquier otra cosa.
- La cita "*--cache-reuse is misleadingly named […]*" proviene de Discussion #22354 (May 2026); el comentario aparece atribuido a ggerganov en cross-references pero verifícalo directamente si vas a citarlo formalmente.
- Speculative decoding con MTP en Gemma 4 E4B (con "centroids masking" para reducir lm_head ~45×) está documentado en `docs.vllm.ai/projects/recipes` para Gemma 4 sobre vLLM, **pero no está disponible en llama.cpp para Gemma 4 al cierre de esta consulta**.
- "Alexa-tier 4-5 s" es un techo total. Con TTS + STT + tool execution real, tu LLM budget práctico está en **~2.5 s por turno máximo**. Asegúrate de medir end-to-end, no sólo prefill+gen.
- Los tamaños de modelo citados (E2B-it Q4_K_M = 3.11 GB en `unsloth/gemma-4-E2B-it-GGUF`, E4B-it Q4_K_M = 5.34 GB en `ggml-org/gemma-4-E4B-it-GGUF`) vienen de los repos oficiales de Hugging Face. Si tu archivo local pesa diferente (p. ej. la versión unsloth de E4B es 4.98 GB), ajusta la aritmética de VRAM pero la conclusión (no entra E4B + E2B en 6 GB) se mantiene.