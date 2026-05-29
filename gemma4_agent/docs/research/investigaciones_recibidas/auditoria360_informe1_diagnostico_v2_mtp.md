# Diagnóstico técnico v2 — Agente de voz local Windows sobre Gemma 4 E4B-it Q4_K_M (llama.cpp b9090): re-corrida con realidad Gemma 4 / MTP

**TL;DR**
- **§7.6 (latencia) corregido:** el drafter MTP oficial de Gemma 4 E4B existe (`google/gemma-4-E4B-it-assistant`, ~78.8M params, Apache 2.0, publicado 5-may-2026), pero **no carga en llama.cpp mainline b9090 ni en ningún commit upstream hasta el 24-may-2026** — la PR #22673 que mergeó MTP el 16-may-2026 es solo Qwen3.6; Gemma 4 con cabeza de centroides E2B/E4B requiere fork (AtomicBot-ai/atomic-llama-cpp-turboquant, reffdev/llama.cpp gemma4-mtp, o ik_llama.cpp PR #1744). La ruta MTP oficial **no está disponible hoy en su runtime**; las opciones reales en b9090 son (a) `--spec-type ngram-cache/ngram-mod` sin drafter, (b) reducir techo de razonamiento por `max_tokens`/grammar (Gemma 4 NO expone budget numérico nativo), o (c) cambiarse a un fork — recomiendo (a)+(b) ahora y monitorear mainline.
- **§7.1 input-injection sigue siendo el bloqueador P0:** la causa raíz (SetForegroundWindow asincrónico cross-thread, SendKeys.SendWait sin esperar procesamiento cross-process, UWP Calculator detrás de ApplicationFrameHost/CoreWindow, y costo CLR de PowerShell por keystroke) está bien establecida en Raymond Chen / Old New Thing; el fix sigue siendo ctypes/pywin32 SendInput in-process con la secuencia canónica `SetForegroundWindow → SendMessageTimeout(WM_NULL) → verify GetForegroundWindow → AttachThreadInput + SendInput`, gated por UIA HasKeyboardFocus, verificación por `AutomationId='CalculatorResults'`.
- **Plan de acción priorizado:** P0 SendInput in-process + verificación UIA (§7.1); P1 gramática GBNF con enum cerrado de tool-names + decoupling razonamiento ↔ tool-call con `<|think|>` togglable y tope por `max_tokens`/stop (§7.2 y §7.6); P2 ngram-cache speculative decoding mientras mainline integra Gemma 4 MTP; P3 mantener `command_splitter`, UIA TextPattern como verificador no-VLM, y RRF híbrido con cabeza de abstención multilingüe.

---

## Lo que sé con evidencia vs. lo que asumo y debe verificarse

**Sé con evidencia (fuente citada):**
- Google publicó MTP drafters para Gemma 4 el **5-mayo-2026** bajo Apache 2.0, para 4 variantes: 31B Dense, 26B A4B MoE, E2B y E4B (blog Google, MarkTechPost, model card `google/gemma-4-E4B-it-assistant`). Runtimes oficialmente integrados: Transformers, MLX, vLLM, SGLang, Ollama, LiteRT-LM. **llama.cpp NO está en esa lista.**
- El drafter E4B comparte embeddings, activaciones y KV-cache del target; tiene cabeza de centroides ordenados (`mtp.centroids.weight` + `mtp.token_ordering.weight`) que comprime el LM head de 262K-vocab a 2048 centroides — un cuello específico del edge (Google AI Docs MTP overview, AtomicChat repo).
- `num_speculative_tokens` recomendados por Google: 2 (E2B), 4 (E4B y 26B-A4B), 4–8 (31B). El drafter es ~4 capas (Google AI Docs MTP).
- **Gemma 4 E4B-it Q4_K_M GGUF = 4.98 GB** (unsloth/gemma-4-E4B-it-GGUF). mmproj-BF16 = 992 MB. Drafter oficial = 159 MB safetensors / 78.6 MB Q4_K_M GGUF (AtomicChat).
- llama.cpp **b9090 fue liberado el 9-may-2026** (GitHub Releases).
- **PR #22673** ("llama + spec: MTP Support") fue mergeada **~16-may-2026**, pero la arquitectura soportada es Qwen3.6 (`--spec-type draft-mtp`); el drafter Gemma 4 carga la arquitectura custom `Gemma4AssistantForCausalLM` que mainline **no reconoce** — el `convert_hf_to_gguf.py` falla (Discussion #22735 abierta y sin respuesta al 24-may-2026; AtomicChat README: *"will not load in stock llama.cpp ... will fail with an unknown architecture error"*).
- Existen 3 forks que **sí** corren Gemma 4 E4B MTP: AtomicBot-ai/atomic-llama-cpp-turboquant, `reffdev/llama.cpp` branch `gemma4-mtp` (reporta 70–87% acceptance, ~60% throughput uplift en E4B), e ik_llama.cpp PR #1744 (mergeada 10-may-2026, foco 31B). Mainline ggml-org/llama.cpp: pendiente al 24-may-2026.
- La extracción comunitaria PyTorch (`SeatownSin/gemma-4-E4B-mtp-drafter`) reporta solo **~35% top-1 acceptance** porque dequantizó pesos INT4/INT8 móviles (ruido irreversible) y advierte: *"each cycle requires ≥2 base model forward passes ... yielding ~0.7x — slower than autoregressive"* en bucles Python; solo vLLM/SGLang con kernels fusionados redimen ese 35%.
- **Gemma 4 NO expone budget numérico de razonamiento nativo.** El model card oficial documenta solo el switch binario `<|think|>` en system prompt y el kwarg `enable_thinking` en Jinja; el único "token budget" mencionado es para tokens visuales (70/140/280/560/1120). El cap numérico en llama.cpp se hace con `--reasoning-budget N` (PR #13771, originalmente para Qwen3/QwQ/DeepSeek-R1), pero en Gemma 4 hay reportes (Discussion #21338) de que `--reasoning-budget 0` y `enable_thinking:false` no siempre suprimen el thinking — hay que validar.
- Llama.cpp expone speculative decoding sin draft model: `--spec-type ngram-cache|ngram-simple|ngram-map-k|ngram-map-k4v|ngram-mod` (cero VRAM extra). Es muy fuerte en prompts repetitivos / RAG y nulo en conversación variada — confirmado por Christopher Maher, *"I tested speculative decoding on my home GPU cluster"* (DEV Community, abril 2026): *"Almost 5x speedup by run 10. I was ready to write a very different article. Then I ran 8 different prompts. Code generation, API design, Go functions, bash scripts, technical explanations. Real variety. Zero improvement."*
- Speculative decoding "tradicional" en sistemas con 6 GB VRAM es típicamente **peor** que autoregresivo porque el draft requiere su propio KV-cache (comentario directo en PR #22673 de un usuario con 6 GB VRAM).
- GBNF en llama.cpp permite restringir output a un enum cerrado de strings (JSON schema → GBNF nativo). La doc advierte: *"Prompting with both a grammar and function calling is not supported due to the nature of how grammar enforcement works"* (node-llama-cpp), y en gpt-oss se reporta que *"function calling internally uses its own grammar, depending on the model"* (Discussion #15341). Para Gemma 4, el tool-calling se hace con `--jinja` y plantilla nativa; agregar una GBNF custom sobre tool-call requiere apagar o componer con la lógica interna.
- TOOLDEC (Chen, Wang et al., *"Don't Fine-Tune, Decode: Syntax Error-Free Tool Use via Constrained Decoding"*, arXiv 2310.07075) confirma textualmente: *"TOOLDEC improves its accuracy in tool use from the initial 0% to an impressive 52%, matching the performance of specialized fine-tuned models such as ToolLLM ... TOOLDEC also eliminates all syntax errors."*
- Raymond Chen (The Old New Thing, 18-nov-2016): *"This notification is processed synchronously if the target window's thread belongs to the same input queue as the thread that is calling SetForegroundWindow, and it is processed asynchronously if the window belongs to a different thread group."* Solución canónica: `SendMessageTimeout(hwndTarget, WM_NULL, ...)` + `GetForegroundWindow()` verify antes de `SendInput`.
- UIAutomation: el resultado de Calculator UWP se lee con `AutomationId="CalculatorResults"` y `CurrentName` devuelve `"Display is <valor>"` (MrExcel reference, Microsoft Learn UIA docs).
- Abstención multilingüe (MKA, arXiv 2503.23687; CausalAbstain, arXiv 2506.00519) confirma que la calibración por idioma mejora abstain accuracy especialmente en idiomas de bajo recurso.
- Cifra "hasta 3x" de Gemma 4 MTP: la fuente original es el Google Blog (5-may-2026) — *"Multi-Token Prediction (MTP) drafters are making Gemma 4 models up to 3x faster at inference"*, replicada literalmente por MarkTechPost (Asif Razzaq, 6-may-2026); no es un consenso independiente sino una sola cifra de Google con benchmark Gemma 4 26B sobre RTX PRO 6000.

**Asumo / debe verificarse contra el código real y b9090:**
- Que su build b9090 fue construido SIN cherry-pick de PR #22673 (b9090 = 9-may-2026, PR mergeada ~16-may-2026 → b9090 NO la incluye; cualquier release ≥ b9100 sí). Verifíquelo con `llama-server --help | grep spec-type`: si no aparece `draft-mtp`, su build no tiene siquiera el camino MTP genérico.
- Que la plantilla Jinja oficial de Gemma 4 inyecta sus propios tokens de tool-call cuando se usa `--jinja`; antes de aplicar GBNF custom sobre tool-name, exporte primero qué genera el modelo sin grammar y luego construya la GBNF "lazy" disparada por el token de inicio de tool-call.
- Que UIA `HasKeyboardFocus` es realmente el predicate correcto para Calculator UWP (debería serlo según el árbol UIA, pero hay variaciones por versión de Windows; valídelo con `inspect.exe` de la Windows SDK).
- Que su 6 GB VRAM efectivo (después de OS + browser) realmente acomoda E4B Q4_K_M (4.98 GB) + KV cache @ contexto 8K-32K. Empíricamente con `-fa on -ctk q8_0 -ctv q8_0` debería caber con ~0.5–0.8 GB libre, pero **márquelo** con `nvidia-smi` durante el peor turno.

---

## §7.6 — Latencia (RE-ESCRITO): la realidad de Gemma 4 MTP + llama.cpp b9090

### Observación medida que justifica esta sección
Decode domina la latencia: p90 = 268 tokens / 4.3 s ≈ 62 tok/s. Con razonamiento ON tool-call es 6/6, OFF es 2/6 — están **acoplados**. El objetivo Alexa-tier es 4–5 s; 8 s es catastrófico. La pregunta correcta no es "¿puedo activar MTP?" sino **"¿qué combinación de (a) reducir tokens y (b) acelerar tokens me deja debajo de 5 s sin romper el tool-calling?"**.

### Tabla comparativa — opciones de aceleración disponibles HOY en llama.cpp b9090

| Opción | Disponibilidad real en b9090 | Ganancia esperada | Costo VRAM | Riesgo / fricción |
|---|---|---|---|---|
| **A. ngram-cache speculative (`--spec-type ngram-cache` o `ngram-mod`)** | ✅ Sí, sin draft model | 1.3–5x en prompts repetitivos / RAG; **~0% en conversación variada** (Maher, DEV) | 0 GB extra | Cero — es opt-in y reversible |
| **B. Drafter MTP oficial Gemma 4 E4B (`google/gemma-4-E4B-it-assistant`)** | ❌ **NO carga en mainline**: arquitectura `Gemma4AssistantForCausalLM` desconocida (Discussion #22735, AtomicChat README) | Reportado 60% uplift en fork reffdev/llama.cpp con 70–87% acceptance en E4B | +0.5–1 GB (drafter Q4_K_M = 78.6 MB + su KV) | Requiere build de fork; mantenimiento manual; abandona b9090 |
| **C. Fork AtomicBot-ai/atomic-llama-cpp-turboquant** | ⚠️ Funciona pero **NO es upstream** | Reporta **+5–7% en Qwen3.6 27B dense y +28–36% en Qwen3.6 35B-A3B MoE** (bench log del propio repo, 12-may-2026; el repo no publica número para E4B) | +0.5 GB + KV; TurboQuant KV cache opcional (`-ctk turbo3`) | Build de fork, divergencia futura, sin auditoría — incompatible con la regla "OSS reproducible mainline" |
| **D. Migrar a vLLM/SGLang con drafter oficial** | ✅ Drafter está en su ruta oficial | Google Blog publicita *"up to 3x faster"* — cifra Google sobre 26B + RTX PRO 6000, no verificada de forma independiente para E4B + 6 GB | Drafter Q4_K_M ~80 MB + activaciones extra; vLLM exige más VRAM base que GGUF (~6–8 GB para E4B FP8/INT4) | Pierde llama.cpp **prefix-cache** del que dependen — recompilar la pipeline, perder reproducibilidad GGUF. **NO recomendado para 6 GB.** |
| **E. Reducir techo de razonamiento (`max_tokens` y/o `--reasoning-budget N`)** | ✅ Disponible | Reduce **tokens generados** directamente — si p90=268, capear thought a 96 puede dejar p90 ≈ 160 → ~2.6 s | 0 GB | **`--reasoning-budget` en Gemma 4 tiene reportes de no suprimir thinking** (Discussion #21338); validar con grammar/stop como respaldo |
| **F. Apagar `<|think|>` completo** | ✅ | Drástica reducción de tokens | 0 GB | **Rompe tool-call 6/6 → 2/6 en su medición** — inaceptable |

### Recomendación principal §7.6
Combinar **A + E** ahora; **B/C solo cuando mainline integre Gemma 4 MTP** (rastrear Discussion #22735 y un PR Gemma4-específico). **NO migrar a vLLM/SGLang** dado su constraint de 6 GB VRAM + dependencia de prefix-cache de llama.cpp.

**Cambio concreto:**
1. Agregue `--spec-type ngram-cache --spec-ngram-size-n 4 --spec-ngram-size-m 16 --draft-max 8` al `llama-server`. Es gratuito y reversible.
2. Cap reasoning a 96–128 tokens con **dos defensas redundantes**:
   - `--reasoning-budget 96` (puede fallar en Gemma 4 — defensa #1).
   - Grammar GBNF que limite el bloque `<|channel|>thought\n…</channel|>` a un número máximo de líneas/tokens, o un stop string en el end-of-thought.
   - Si ambos fallan, post-procesar el SSE: cortar el thought al token 96 y forzar emitir `</channel|>` como token de stop.
3. Mantener `<|think|>` ON (porque OFF mata el tool-calling).

**Validación mínima medible:**
- 30 prompts representativos × {ngram off, ngram on} × {budget {64, 96, 128, full}}. Medir tok/s decode, p50/p90 latencia E2E, **y tool-call success 6/6 (la métrica de regresión crítica)**. Aceptar el setting más rápido que mantenga ≥5/6.
- Espere: ngram-cache solo da uplift en prompts con repetición (RAG, citado del contexto). En diálogo conversacional variado **acepte ~0% mejora de ngram** y dependa del budget de razonamiento.

### Cuándo (y solo entonces) activar MTP oficial
Active el drafter MTP E4B **solo cuando se cumpla esto** (probablemente julio–agosto 2026):
- Discussion #22735 cierre con un PR mergeado en `ggml-org/llama.cpp`, **o**
- Aparezca un release tag (≥ b91xx) cuyo changelog mencione `Gemma4Assistant` / `gemma4_assistant` / centroid head.
- Verifique con: `llama-server --help | grep -E "draft-mtp|gemma4"` y `convert_hf_to_gguf.py --help` listando la arquitectura.

Hasta entonces, **no use** ni la extracción `SeatownSin/gemma-4-E4B-mtp-drafter` ni los forks AtomicBot/reffdev en producción: la extracción tiene 35% acceptance + 0.7x slowdown documentado por su propio autor, y los forks rompen la trazabilidad OSS/mainline.

---

## §7.1 — Input injection contra UWP Calculator (RE-VALIDADO, sigue siendo P0)

### Diagnóstico (sin cambios — sigue correcto)
El patrón observado (caracteres iniciales perdidos: "3" en lugar de "53", "5" en lugar de "5+0=", "0" colgada) es **completamente consistente** con la documentación de Raymond Chen:

1. **`SetForegroundWindow` es asincrónico cross-thread.** Cita directa de The Old New Thing (Microsoft DevBlogs, Raymond Chen, 18-nov-2016): *"This notification is processed synchronously if the target window's thread belongs to the same input queue ... and asynchronously if the window belongs to a different thread group."* En PowerShell → ApplicationFrameHost.exe → CoreWindow son **tres thread groups distintos**.
2. **`SendKeys.SendWait` no espera procesamiento cross-process.** Es un método CLR del thread llamador y no bloquea hasta que la ventana destino procese su cola.
3. **UWP Calculator vive en ApplicationFrameHost.exe** como wrapper, con el control real en un CoreWindow hijo; SendKeys aterriza en el frame, no en el child que tiene focus.
4. **CLR cold-start por keystroke en PowerShell** explica la dependencia carga del sistema: en máquina fresca (chains5/chains6) 100%, saturada (ref/final) 25–50% — el JIT no alcanza a "calentar" entre invocaciones consecutivas.

### Solución (sin cambios — sigue siendo la canónica)
Migrar de **process-per-keystroke → in-process Win32**. La precedente exacta es **microsoft/PowerToys PR #1282** ("*SendInput hack to workaround the SetForegroundWindow bug — Use AttachThreadInput to be able to workaround the SetForegroundWindow bug. As described by Raymond Chen, the main issue with attaching the input queue of another application is that our thread could hang*"), por lo que el patrón production-grade incluye `AttachThreadInput` con timeout, no `SendInput` desnudo.

```python
# Pseudocódigo del fix
import ctypes, win32gui, win32con, comtypes.client as cc
SetForegroundWindow(hwnd_calc)                           # 1. async
SendMessageTimeout(hwnd_calc, WM_NULL, 0, 0,
                   SMTO_ABORTIFHUNG, 5000, None)         # 2. wait until WA_INACTIVE pumped
assert GetForegroundWindow() == hwnd_calc                # 3. verify
# 4. AttachThreadInput para que el SetFocus al CoreWindow hijo sea efectivo,
#    aceptando el riesgo Chen ("Get Into the Same Jail Card") con timeout:
AttachThreadInput(my_tid, target_tid, True)
try:
    SetFocus(core_window_child_hwnd)
    uia = cc.CreateObject("UIAutomationClient.CUIAutomation")
    elem = uia.ElementFromHandle(core_window_child_hwnd)
    # gate por UIA, no por "foreground stable 2 reads":
    assert elem.GetCurrentPropertyValue(UIA_HasKeyboardFocusPropertyId)
    assert elem.GetCurrentPropertyValue(UIA_IsEnabledPropertyId)
    # 5. SendInput con KEYEVENTF_UNICODE (no scan codes / VK_)
    SendInput(inputs)
finally:
    AttachThreadInput(my_tid, target_tid, False)
# 6. Verificación: leer CalculatorResults via UIA, no dHash
result_elem = elem.FindFirst(TreeScope_Descendants,
   uia.CreatePropertyCondition(UIA_AutomationIdPropertyId, "CalculatorResults"))
display = result_elem.CurrentName  # "Display is 53"
```

**Validación mínima medible:**
- Re-correr exactamente los mismos casos `chains5/chains6/ref/final` × {máquina fresca, máquina saturada con ~80% CPU}. Esperado: 100% éxito en ambos perfiles y desaparición de la dependencia carga-del-sistema. Si NO sucede, el problema secundario es UIA `HasKeyboardFocus` en el CoreWindow hijo — fallback adicional: enumerar `EnumChildWindows` y mandar `SendInput` con `AttachThreadInput` ya activado.

---

## §7.2 — Hallucination en tool-name (el 4B emite `system(action='calculator')`)

### Cambio concreto
Decodificación restringida con **GBNF con enum cerrado de tool-name**, disparada lazy por el token de apertura de tool-call de la plantilla nativa de Gemma 4.

```gbnf
# tool_call.gbnf (lazy: trigger en el token de open tool-call de la Jinja Gemma 4)
root        ::= tool-open ws? tool-body ws? tool-close
tool-open   ::= "<tool_call>"        # ajustar al token real exportado por la plantilla
tool-close  ::= "</tool_call>"
tool-body   ::= "{" ws "\"name\":" ws tool-name ws "," ws "\"args\":" ws args "}"
tool-name   ::= "\"open_app\"" | "\"calc_eval\"" | "\"set_volume\"" | "\"get_time\""
args        ::= "{" (string ":" value ("," string ":" value)*)? "}"
```

**Por qué:** TOOLDEC (Chen, Wang et al., arXiv 2310.07075) — *"TOOLDEC improves its accuracy in tool use from the initial 0% to an impressive 52%, matching the performance of specialized fine-tuned models such as ToolLLM ... TOOLDEC also eliminates all syntax errors."* La GBNF de llama.cpp es semánticamente equivalente al FSM de TOOLDEC y soporta enums nativos vía la conversión `json_schema_to_grammar.py`.

**Caveat crítico:** llama.cpp ya tiene una grammar interna activada por `--jinja` cuando detecta tool-calling en la plantilla; agregar grammar custom encima puede *componer mal* (ver Discussion #15341 sobre gpt-oss: *"function calling internally uses its own grammar, depending on the model"*). Use `--reasoning-format none` y emita la grammar como **lazy grammar** (sintaxis con `trigger_tokens` documentada en `grammars/README.md` de llama.cpp). Si no compone, fallback: post-validate en el cliente, rechazar y re-prompt — más caro pero correcto y conforme a "no hardcodes".

**Validación mínima medible:**
- Set de 50 turnos donde el 4B previamente alucinó `system(...)`. Con la GBNF, debería ser 0/50 nombres inválidos, y la tasa de tool-call correcto subir desde su baseline. Si la GBNF compone mal con el `--jinja` interno, lo verá por errores 400/500 del server o por output corrupto.

---

## §7.3 — El 4B no encadena pasos (0/12 en 2-step)

### Cambio concreto
**Mantener** el `command_splitter` determinístico (ya existe, ya funciona). No intentar resolver con prompting — la literatura es clara: en multi-step planning benchmarks, los modelos top-tier todavía caen ~20–40 puntos entre single-step y multi-step. Un 4B local no va a cerrar esa brecha con prompt engineering.

**Asegurar que el splitter NO sea per-language regex** — debe ser estructural (delimitadores universales: conectores coordinantes, comas entre verbos imperativos consecutivos) o, mejor, una segunda llamada al LLM con un grammar GBNF que **fuerce JSON array de sub-intents**. Esto cumple "no hardcodes/canned" y "multilingüe universal".

**Validación mínima medible:** los mismos 12 prompts de 2-step en {ES, EN, PT, FR}, midiendo splits válidos (forma) y ejecución end-to-end. Threshold: ≥9/12 en cada idioma.

---

## §7.4 — dHash no es confiable para texto pequeño

### Cambio concreto
Reemplazar `dHash(screenshot)` por lectura UIA del control de resultado:
- Para Calculator UWP: `AutomationId="CalculatorResults"`, leer `CurrentName` que devuelve `"Display is <valor>"`, parsear con `s.split(" is ")[-1]`.
- Para apps generales sin AutomationId estable: `TextPattern.DocumentRange.GetText()` o `LegacyIAccessiblePattern`.
- Esto es el verificador **OS-state** universal exigido por la restricción "verify by OS state, never tool returned ok" — y es mucho más barato que un VLM por turno.

**Caveat:** algunas apps Win32 antiguas no exponen UIA correctamente; para esos casos, fallback gated al `mmproj` (último recurso).

**Validación mínima medible:** 20 verificaciones de cálculo, comparar UIA-read vs ground truth, esperando 20/20.

---

## §7.5 — Router multilingüe mis-routing

### Cambio concreto
Mantener arquitectura sin hardcodes per-language. La mejora viene de:
1. **Cabeza de abstención calibrada per-idioma** (MKA, arXiv 2503.23687; CausalAbstain, arXiv 2506.00519): cuando la probabilidad top-1 del clasificador embedding está por debajo de un threshold calibrado por idioma, abstain → pedir clarificación en el idioma del usuario (no en inglés). La calibración por idioma es **necesaria** porque los embeddings multilingües tienen escalas distintas — un threshold global discrimina mal a low-resource (CausalAbstain).
2. **Fusión RRF (Reciprocal Rank Fusion)** entre embedding-classifier y LLM zero-shot, también per-idioma; esto cumple "estructural, no keyword-list" y mejora robustez según el benchmark multilingüe jerárquico (arXiv 2603.23172, que muestra que evaluaciones traducidas sobreestiman ~10–20 puntos vs queries reales).

**Validación mínima medible:** held-out 100 queries × 4 idiomas, medir routing accuracy y abstain precision/recall por idioma. Calibrar threshold por idioma con conjunto disjunto, no global.

---

## Restricciones duras — verificación de cumplimiento

| Restricción | Cumplimiento del plan |
|---|---|
| OSS y free, sin APIs pagas | ✅ llama.cpp + GGUF + UIA + GBNF + embeddings locales |
| vram4 (E4B-it Q4_K_M, monoslot, 6 GB VRAM) | ✅ 4.98 GB modelo + KV @ 8K en q8 ≈ 0.5–0.8 GB → cabe; el drafter MTP **no aplica hoy** así que no consume VRAM extra |
| STT en CPU | ✅ no se toca |
| mmproj (~990 MB) gated | ✅ solo fallback de verificación cuando UIA falla |
| Latencia tier-Alexa 4–5 s | ⚠️ Alcanzable solo combinando budget de razonamiento (96–128 thought tokens) + ngram-cache; **no garantizable** sin MTP — documentar como riesgo |
| Sin hardcodes / canned | ✅ embeddings + structural splitters + UIA |
| Multilingüe / multi-usuario | ✅ calibración per-idioma simétrica |
| Verify by OS state | ✅ UIA reads, no "tool returned ok" |

---

## Recomendaciones priorizadas (qué cambiar, por qué, validación)

### P0 — input injection (§7.1)
- **Qué:** migrar de `Start-Process powershell ... SendKeys` por keystroke a `ctypes/pywin32 SendInput` in-process con secuencia Chen (`SetForegroundWindow → SendMessageTimeout(WM_NULL,5000) → GetForegroundWindow verify → AttachThreadInput → SetFocus al CoreWindow → UIA HasKeyboardFocus/IsEnabled gate → SendInput KEYEVENTF_UNICODE → DetachThreadInput → leer CalculatorResults UIA`).
- **Por qué:** Raymond Chen (Microsoft DevBlogs) documenta la asincronía cross-thread; microsoft/PowerToys PR #1282 valida que la solución correcta es `AttachThreadInput` con timeout (no `SendInput` desnudo).
- **Validación:** `chains5/chains6/ref/final × {fresca, saturada}` → 100% en ambos.

### P1a — tool-name hallucination (§7.2)
- **Qué:** GBNF lazy con enum de tool-names, disparada por token de open-tool-call de plantilla Gemma 4.
- **Por qué:** TOOLDEC (arXiv 2310.07075) — *"from the initial 0% to an impressive 52% ... eliminates all syntax errors"*.
- **Validación:** 50 turnos previamente fallidos → 0 tool-names inválidos.

### P1b — desacoplar razonamiento ↔ tool-call (§7.6)
- **Qué:** mantener `<|think|>` ON pero cap thought block a ≤96 tokens vía `--reasoning-budget 96` + stop string redundante.
- **Por qué:** ON da 6/6 tool-calls, pero los 268 tokens p90 son el cuello. Capear thought no apaga reasoning.
- **Validación:** 6/6 → ≥5/6 tolerable; p90 latencia debajo de 5 s en ≥80% de turnos.

### P2 — speculative decoding sin VRAM extra (§7.6)
- **Qué:** `--spec-type ngram-cache --spec-ngram-size-n 4 --draft-max 8` en `llama-server`.
- **Por qué:** gratis, reversible, gana en prompts con repetición (RAG / citado del contexto); cero riesgo.
- **Validación:** A/B con y sin, en 30 prompts de conversación real.

### P3 — verificación universal (§7.4) y router multilingüe (§7.5)
- **Qué:** UIA `TextPattern` reads, RRF + abstain calibrado per-idioma.
- **Por qué:** UIA es OS-state real; CausalAbstain (arXiv 2506.00519) muestra mejora en low-resource lang.
- **Validación:** 20 cálculos UIA-read vs ground truth; 100 queries × 4 idiomas para router.

### P4 (en monitoreo, NO actuar hoy) — MTP oficial Gemma 4 (§7.6)
- **Cuándo activar:** Discussion #22735 cerrada con merge en mainline `ggml-org/llama.cpp`, o un release tag (≥ b91xx) que liste `Gemma4Assistant` en `convert_hf_to_gguf.py`. Hasta entonces, NO usar SeatownSin (35% acceptance, 0.7x slowdown autoconfirmado por su autor) ni forks (rompen reproducibilidad mainline).
- **Threshold para reconsiderar:** si Discussion #22735 sigue sin progreso al 1-julio-2026 y la latencia es bloqueador comercial, evaluar AtomicBot fork con disclaimer de mantenimiento.

---

## Caveats finales

- **b9090 fecha:** 9-may-2026. PR #22673 (MTP genérico) mergeada ~16-may-2026 → b9090 **no la incluye**. Verifíquelo localmente: `./llama-server --help | grep spec-type` — si no aparece `draft-mtp`, su build ni siquiera tiene el camino MTP de Qwen3.6, y necesita ≥ b9100.
- **`--reasoning-budget` en Gemma 4:** Discussion #21338 reporta que `--reasoning-budget 0` y `enable_thinking:false` no siempre suprimen el `<think>` en Gemma 4. Su mitigación debe llevar **doble defensa**: budget numérico + grammar/stop string. Verifíquelo grabando salidas raw con `--verbose`.
- **Si la grammar de tool-call compone mal con `--jinja`:** caer a post-validación cliente con re-prompt; es subóptimo pero correcto.
- **Si UIA `HasKeyboardFocus` no funciona en el CoreWindow hijo de Calculator UWP:** caer a `EnumChildWindows` + `AttachThreadInput` con timeout + `SetFocus` (Get Into the Same Jail Card de Chen — costoso pero determinístico).
- **La cifra "3x" de Google es una sola medición** (Gemma 4 26B sobre NVIDIA RTX PRO 6000, blog Google 5-may-2026); en E4B + 6 GB VRAM nadie ha publicado independientemente un número similar. Los reportes de forks (Atomic, reffdev) son ~1.6–1.9x en otras combinaciones, no 3x.
- **Reportes externos fallan en detalles de entorno:** todas las cifras y configuraciones aquí deben verificarse contra (a) el código actual del agente, (b) el binario b9090 exacto que están usando, (c) la versión de Windows (10 vs 11) — los AutomationIds de Calculator difieren entre versiones.

---

## Fuentes
- Google Blog — Accelerating Gemma 4 with MTP drafters: https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/
- Google AI Docs — MTP overview: https://ai.google.dev/gemma/docs/mtp/overview
- Google AI Docs — Gemma 4 model card: https://ai.google.dev/gemma/docs/core/model_card_4
- Google AI Docs — Gemma 4 MTP with HF Transformers: https://ai.google.dev/gemma/docs/mtp/mtp
- MarkTechPost — Gemma 4 MTP release (6-may-2026): https://www.marktechpost.com/2026/05/06/google-ai-releases-multi-token-prediction-mtp-drafters-for-gemma-4-delivering-up-to-3x-faster-inference-without-quality-loss/
- HuggingFace — google/gemma-4-E4B-it-assistant (drafter oficial): https://huggingface.co/google/gemma-4-E4B-it-assistant
- HuggingFace — SeatownSin/gemma-4-E4B-mtp-drafter (extracción comunitaria, 35% acceptance disclaimer): https://huggingface.co/SeatownSin/gemma-4-E4B-mtp-drafter
- HuggingFace — AtomicChat/gemma-4-E4B-it-assistant-GGUF (fork, "will not load in stock llama.cpp"): https://huggingface.co/AtomicChat/gemma-4-E4B-it-assistant-GGUF
- HuggingFace — unsloth/gemma-4-E4B-it-GGUF (Q4_K_M = 4.98 GB, mmproj-BF16 = 992 MB): https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF
- llama.cpp release b9090 (9-may-2026): https://github.com/ggml-org/llama.cpp/releases/tag/b9090
- llama.cpp Discussion #22735 (`Gemma4AssistantForCausalLM` support request, abierta al 24-may-2026): https://github.com/ggml-org/llama.cpp/discussions/22735
- llama.cpp PR #22673 (MTP support, merged ~16-may-2026, solo Qwen3.6): https://github.com/ggml-org/llama.cpp/pull/22673
- llama.cpp Discussion #21338 (Gemma 4 `--reasoning-budget` broken reports): https://github.com/ggml-org/llama.cpp/discussions/21338
- llama.cpp `docs/speculative.md` (ngram-cache types y `--spec-type`): https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
- llama.cpp `grammars/README.md` (GBNF, lazy grammar, JSON-schema-to-GBNF): https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- llama.cpp Discussion #15341 (grammar vs internal function-calling grammar): https://github.com/ggml-org/llama.cpp/discussions/15341
- Christopher Maher — *"I tested speculative decoding on my home GPU cluster"* (DEV Community): https://dev.to/defilan/i-tested-speculative-decoding-on-my-home-gpu-cluster-heres-why-it-didnt-help-3ej6
- Raymond Chen — SetForegroundWindow async (Old New Thing, 18-nov-2016): https://devblogs.microsoft.com/oldnewthing/20161118-00/?p=94745
- Raymond Chen — sharing input queue makes async sync: https://devblogs.microsoft.com/oldnewthing/20130607-00/?p=4143
- microsoft/PowerToys PR #1282 — `AttachThreadInput` para SetForegroundWindow: https://github.com/microsoft/PowerToys/pull/1282
- Microsoft Learn — UIA Verify y TextPattern: https://learn.microsoft.com/en-us/windows/win32/winauto/ui-automation-verify
- MrExcel — `CalculatorResults` `AutomationId` reference: https://www.mrexcel.com/board/threads/using-uiautomation-to-automate-the-windows-10-calculator.1137758/
- arXiv 2310.07075 — TOOLDEC (constrained decoding, *"from 0% to 52% ... eliminates all syntax errors"*): https://arxiv.org/abs/2310.07075
- arXiv 2503.23687 — MKA (multilingual abstention): https://arxiv.org/abs/2503.23687
- arXiv 2506.00519 — CausalAbstain: https://arxiv.org/html/2506.00519
- arXiv 2603.23172 — Multilingual intent benchmark (native vs translated): https://arxiv.org/abs/2603.23172