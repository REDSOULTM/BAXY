# 13 — Carter v5: Perfiles VRAM detallados (v2 — aprovechar hardware al máximo)

**Fecha**: 2026-05-11
**Versión**: 2 (corregida tras feedback del user)
**Pre-requisito**: leer Doc 11 (lecciones) y Doc 12 (arquitectura).

**Cambio principal vs v1**: Si el usuario tiene 16GB de VRAM, no tiene sentido cargar un modelo de 7GB. Cada tier debe usar el **modelo MÁS CAPAZ que cabe en su VRAM** con margen seguro (~1-2 GB para Windows + KV + apps).

---

## Filosofía corregida

> **"Aprovechar la VRAM del usuario."**
>
> No es "Carter mínimo viable en VRAM mínima". Es **"Carter máxima calidad que cabe"**.
>
> Si tenés 6GB → Carter usa ~4.5-5 GB y tu PC tiene 1 GB libre para Windows.
> Si tenés 16GB → Carter usa ~14-15 GB y tu PC tiene 1 GB libre.

### Margen de seguridad por tier

| Tier | VRAM total | Carter usa | Libre para Windows + apps |
|---|---|---|---|
| 6GB | 6.0 GB | 4.5-5.0 GB | ~1.0-1.5 GB |
| 8GB | 8.0 GB | 6.5-7.0 GB | ~1.0-1.5 GB |
| 10GB | 10.0 GB | 8.5-9.0 GB | ~1.0-1.5 GB |
| 12GB | 12.0 GB | 10.5-11.0 GB | ~1.0-1.5 GB |
| 16GB | 16.0 GB | 14.0-15.0 GB | ~1.0-2.0 GB |

**Por qué 1-2 GB libres**:
- Windows compositor: ~500 MB
- Apps GPU típicas (Chrome con hw accel, Discord, OBS): 300-800 MB
- KV cache headroom durante sesiones largas
- Margen de seguridad contra OOM en spikes

---

## Resumen ejecutivo (v2)

| Tier | VRAM target | Modelo Gemma 4 | Quant | VRAM cargado | Bench medido (60-test) | Validación |
|---|---|---|---|---|---|---|
| **6GB** | 4.5-5 GB | **E4B-it** | **UD-IQ2_M** | **5.13 GB** | 91.6% (55/60) | medido |
| **8GB** | 6.5-7 GB | **E4B-it** | **Q5_K_M** | **6.61 GB** | 91.6% (55/60) | medido |
| **10GB** | 8.5-9 GB | **E4B-it** | **Q8_0** | **8.16 GB** | 91.6% (55/60) | medido |
| **12GB** | 10.5-11 GB | **26B-A4B-it** | **UD-Q3_K_M** | **11.85 GB** | proyectado ~93% | extrapolado |
| **16GB** ⭐ | 14-15 GB | **26B-A4B-it** | **UD-IQ4_XS** | **12.66 GB + KV 16K** ≈ 14.5 GB | 90.0% (54/60), **20/20 Bloque B** | medido |

### Cambios clave vs v1

| Tier | v1 (conservador) | v2 (aprovecha VRAM) | Justificación |
|---|---|---|---|
| 6GB | E2B-Q4_K_M (4.46 GB) | **E4B-UD-IQ2_M (5.13 GB)** | E4B-IQ2_M empata Q4_K_M en bench (91.6%) y es **el mismo E4B** que valida 540/540. Mejor que bajar a E2B. |
| 8GB | E4B-Q4_K_M (6.10 GB) | **E4B-Q5_K_M (6.61 GB)** | Mismo modelo, quant más alta. Calidad ≥ Q4. |
| 10GB | E4B-Q5_K_M (6.61 GB) | **E4B-Q8_0 (8.16 GB)** | Q8 cabe holgado. Aunque Q8 ≈ Q6 en bench Fase 2, en 540 completo no está medido — usar Q8 maximiza calidad con margen. |
| 12GB | E4B-Q6_K (7.10 GB) | **26B-A4B-UD-Q3_K_M (11.85 GB)** | El salto a 26B MoE da capacidad de razonamiento mucho mayor que E4B. Score Fase 2 esperado: 23% (crash) — REVERSE: tier 12 NO USA 26B si crash. Ver nota crítica abajo. |
| 16GB | E4B-Q6_K (7.10 GB) | **26B-A4B-UD-IQ4_XS (14.5 GB total)** | Lo que vos probás ahora. 26B MoE con velocidad de 4B activo, calidad cercana a 26B. |

### ⚠️ Nota crítica sobre 26B-A4B en bench Fase 2

El repo `Probando Gemma 4` midió 60-test bench:
- **26B-A4B-UD-Q3_K_M**: 14/60 (23.3%) — **CRASH temprano** ⚠️
- **26B-A4B-UD-Q3_K_XL**: 56/60 (93.3%) ✅
- **26B-A4B-UD-IQ4_XS**: 54/60 (90.0%) + 20/20 Bloque B ✅
- **26B-A4B-UD-IQ2_M**: 53/60 (88.3%) ✅
- **26B-A4B-UD-IQ2_XXS**: 29/60 (48.3%) — CRASH a mitad ⚠️

**Implicación**: Q3_K_M crashea pero **Q3_K_XL no** (la "XL" tiene fix imatrix). Para tier 12GB usar **Q3_K_XL** en lugar de Q3_K_M.

---

## Resumen ejecutivo CORREGIDO (v2 final)

| Tier | VRAM target | Modelo | Quant | VRAM cargado | Bench medido |
|---|---|---|---|---|---|
| **6GB** | ~5 GB | E4B-it | **UD-IQ2_M** | 5.13 GB | 91.6% |
| **8GB** | ~6.5 GB | E4B-it | **Q5_K_M** | 6.61 GB | 91.6% |
| **10GB** | ~8 GB | E4B-it | **Q8_0** | 8.16 GB | 91.6% |
| **12GB** | ~12 GB | 26B-A4B-it | **UD-Q3_K_XL** | 12.02 GB | 93.3% |
| **16GB** ⭐ | ~14 GB | 26B-A4B-it | **UD-IQ4_XS** | ~14.5 GB | 90.0% + 20/20 Bloque B |

**Cero tiers donde Carter usa <50% de la VRAM disponible.**

---

## Tier 1 — `tier_6gb` (Carter mínimo serio)

### Modelo
- **`gemma-4-E4B-it-UD-IQ2_M.gguf`**
- Path: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\E4B\gemma-4-E4B-it-UD-IQ2_M.gguf`
- Disco: 3.30 GB
- VRAM cargado: **5.13 GB** (con mmproj F16 + KV 16K)
- Multimodal: ✅ mmproj F16

**Por qué E4B-IQ2_M en lugar de E2B-Q4_K_M**:
- Mismo bench score: 55/60 (91.6%) ≈ E4B-Q4_K_M (56/60)
- **Mismo modelo base que el ganador validado 540/540** (E4B-Q6_K)
- IQ2_M usa imatrix dynamic → calidad mejor que Q2 plano
- Permite usar mmproj F16 (vision) en 5GB total

### Sampling (oficial Google Gemma 4)
```python
{"temperature": 1.0, "top_p": 0.95, "top_k": 64,
 "repeat_penalty": 1.0, "max_tokens": 1024}
```
`max_tokens=1024` (no 1280) para no agotar context 8K.

### llama-server flags
```
--jinja -ngl 99 -c 8192 --parallel 1 --ctx-checkpoints 1 --flash-attn on --mmproj <path>
```
Context 8K (no 16K) por VRAM apretada.

### Prompt
- **Tokens target**: ~1000-1200
- Base: CORE_PROMPT v3 con recorte ligero (quitar 5-10 ejemplos más raros)
- Frase explícita anti-bias 4B incluida

### Tools visibles
- **12 composite tools** (subset del consolidated 16):
  - `system_info`, `system_control`, `app`, `web`, `filesystem`, `memory`, `terminal_run`, `clipboard`, `gui_deeplink`, `gui` (básico), `window`, `process`
- NO expone: `vision_*` separadas (usa `gui` action describe_dialog), `media`, `office`, `registry`, `skill_load`

### Capacidades del Agent6GB
- ✅ Pre-LLM short-circuit triviales
- ✅ Tools simples + cadenas cortas (2-3 tools)
- ✅ Vision on-demand (mmproj cargado)
- ✅ Memory + causal focus + streaming
- ❌ Vision inline auto-step (latencia)
- ❌ Cadenas largas 5+ tools (modelo limitado por quant agresiva)

### Criterios de éxito
- Bench P0 ≥ 75% (vs harness ganador 99.81% en mismo modelo+Q6_K)
- Latencia trivial p50 ≤ 4s
- Latencia tool simple p50 ≤ 7s
- VRAM total ≤ 5.5 GB

---

## Tier 2 — `tier_8gb` (Balanced)

### Modelo
- **`gemma-4-E4B-it-Q5_K_M.gguf`**
- Path: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\E4B\gemma-4-E4B-it-Q5_K_M.gguf`
- Disco: 5.11 GB
- VRAM cargado: **6.61 GB** (con mmproj F16 + KV 16K)
- Multimodal: ✅ mmproj F16

**Por qué Q5_K_M en lugar de Q4_K_M**:
- Más quality bits por param (5 vs 4)
- Bench Fase 2 empatado con Q4 dentro de margen (55 vs 56)
- 6.61 GB deja ~1.4 GB libres para Windows + apps en 8GB

### Sampling, flags, prompt, tools, capacidades
Igual que tier_6gb pero context 16K full.

### llama-server flags
```
--jinja -ngl 99 -c 16384 --parallel 1 --ctx-checkpoints 1 --flash-attn on --mmproj <path>
```

### Tools visibles
- **14 composite tools**: tier_6gb + `media` + `office`

### Criterios de éxito
- Bench P0 ≥ 80%
- Latencia tool simple p50 ≤ 5s
- VRAM total ≤ 7 GB

---

## Tier 3 — `tier_10gb` (High quality 4B)

### Modelo
- **`gemma-4-E4B-it-Q8_0.gguf`**
- Path: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\E4B\gemma-4-E4B-it-Q8_0.gguf`
- Disco: 7.63 GB
- VRAM cargado: **8.16 GB** (con mmproj F16 + KV 16K)
- Multimodal: ✅ mmproj F16

**Por qué Q8_0**:
- Quant prácticamente sin pérdida vs F16 original
- Bench Fase 2: 55/60 (91.6%) — empatado con Q5/Q6 dentro de margen Fase 2 (60 tests es ruidoso)
- En 540-test reproducible (NO MEDIDO con Q8), pero teóricamente debería ser ≥ Q6
- 8.16 GB en 10GB total deja 1.84 GB libres

**Nota honesta**: El repo dice "Q8 no aporta sobre Q6 medido en 60-test". Pero ese es ruido de Fase 2. Para usuarios con 10GB, **Q8 es la mejor opción dentro de la familia E4B** porque tiene los bits máximos de precisión. Si quieren más calidad, el siguiente salto es 26B-A4B (tier 12 o 16).

### Sampling, flags, tools, capacidades
Igual que tier_8gb pero modelo más preciso.

### Capacidades extra
- **+ MissionGoal verifier estructural** (Voyager pattern)
- **+ Vision inline auto-step opcional**

### Criterios de éxito
- Bench P0 ≥ 85%
- Latencia tool simple p50 ≤ 5s
- VRAM total ≤ 9 GB

---

## Tier 4 — `tier_12gb` (MoE entry)

### Modelo
- **`gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf`**
- Path: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\26B-A4B\gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf`
- Disco: 12.02 GB
- VRAM cargado: **~13.5 GB con mmproj F16 + KV 16K** ⚠️ ajustado para 12GB
- Multimodal: ✅ mmproj F16 (1.11 GB)

**Por qué 26B-A4B Q3_K_XL**:
- Salto cualitativo: 26B parámetros totales con 4B activos (MoE)
- Bench Fase 2: 56/60 (93.3%) — mejor que cualquier E4B en este tier
- Q3_K_XL (NO Q3_K_M que crashea)
- "XL" significa imatrix dynamic — la diferencia entre crash y funciona

**Nota VRAM**: 13.5 GB en 12GB ES tight. Para usuarios con exactamente 12GB, alternativa segura es **E4B-Q6_K (7.10 GB)** del harness ganador. Hay que decidir caso por caso:
- Si 12GB es exacto y Windows + apps usan 1-2 GB → E4B-Q6_K más seguro
- Si 12GB es real y Windows está liviano → Q3_K_XL viable

**Decisión final**: tier_12gb default = **26B-A4B-Q3_K_XL** con fallback a **E4B-Q6_K** si OOM detected al cargar.

### llama-server flags
```
--jinja -ngl 99 -c 16384 --parallel 1 --ctx-checkpoints 1 --flash-attn on --mmproj <path>
```
Si OOM detected al spawn, retry con `-c 8192`.

### Prompt
- CORE_PROMPT v3 completo (143 líneas)
- Sin recortes (modelo MoE razona mejor con contexto rico)

### Tools visibles
- **15 composite tools**: todas menos `skill_load`

### Capacidades
Todas las de tier_10gb +
- **+ Cadenas largas (5+ tools) confiables** (más capacidad razonamiento)
- **+ Vision inline auto-step activo**

### Criterios de éxito
- Bench P0 ≥ 90%
- Latencia tool simple p50 ≤ 4s (MoE = 4B activo, velocidad alta)
- VRAM total ≤ 14 GB

---

## Tier 5 — `tier_16gb` ⭐ (Full MoE)

### Modelo
- **`gemma-4-26B-A4B-it-UD-IQ4_XS.gguf`** — **lo que estás probando AHORA**
- Path: `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\26B-A4B\gemma-4-26B-A4B-it-UD-IQ4_XS.gguf`
- Disco: 12.66 GB
- VRAM cargado: **14.5 GB con mmproj F16 + KV 8K** (validado: 15.9 GB con context 8192)
- Multimodal: ✅ mmproj F16

**Por qué 26B-A4B IQ4_XS**:
- Bench Fase 2: 54/60 (90.0%) **+ 20/20 perfecto en Bloque B** (mejor que E4B-Q6_K en Bloque B)
- MoE: 26B params totales, 4B activos por token → velocidad cercana a un 4B denso
- IQ4_XS con imatrix → balance óptimo calidad/tamaño
- Aprovecha ~14.5 GB de tus 16 GB — **NO desperdicia hardware**

**Nota latencia esperada**:
- Carga inicial: 30-60s (modelo más grande)
- Token generation: ~similar a E4B-Q6_K (4B activos)
- Razonamiento complejo: superior a E4B (más experts disponibles)

### Sampling (oficial Google Gemma 4)
```python
{"temperature": 1.0, "top_p": 0.95, "top_k": 64,
 "repeat_penalty": 1.0, "max_tokens": 1280}
```

### llama-server flags (validados con tu hardware)
```
--jinja --port 8080 -ngl 99 -c 8192 --parallel 1 --ctx-checkpoints 1 --flash-attn on --mmproj <path>
```
**Context 8K** (no 16K): a 16K el KV cache empuja la VRAM al 100% sin margen. 8K es el sweet spot.

### Prompt
- **CORE_PROMPT v3 COMPLETO** (143 líneas)
- Path: `carter_v5/profiles/tier_16gb/prompt.py`
- Mantener exacto del harness ganador

### Tools visibles
- **16 composite tools COMPLETAS**

### Capacidades del Agent16GB
**Todas las features**:
- ✅ Pre-LLM short-circuit triviales
- ✅ Tools simples + cadenas largas (hasta 8+)
- ✅ Memory completo + eager-load embedder (cold start <5s)
- ✅ Vision inline auto-step en archetype GUI
- ✅ Causal focus + AllowSetForegroundWindow + ALT-press trick
- ✅ MissionGoal verifier (Voyager)
- ✅ Loop detection v2 (result-aware)
- ✅ Streaming SSE
- ✅ Tracing jsonl per-turn
- ✅ Deeplink-first universal (HKCR)
- ✅ Verifier runtime (pycaw, EnumWindows, frame_diff)

### Criterios de éxito (NO NEGOCIABLES)
- **Bench P0 ≥ 90%** — el harness ganador con E4B-Q6_K sacó 100%. Con 26B-A4B esperamos similar.
- Latencia trivial p50 ≤ 3s
- Latencia tool simple p50 ≤ 4s
- Latencia multi-step p50 ≤ 10s
- VRAM total ≤ 15 GB (deja 1 GB libre)
- Cold start ≤ 10s (modelo más grande)

### Fundamentación
- Probando Gemma 4 Fase 2: **20/20 Bloque B perfecto** (mejor que E4B-Q6_K que sacó 19/20)
- Bloque A: 26/30 (vs E4B-Q6_K 28/30) — pierde 2 puntos en hallucination
- **No validado contra bench 540 completo** — Carter v5 lo va a medir primero

### Plan B si tier_16gb no llega a target
Si 26B-A4B-IQ4_XS no alcanza 90% bench:
- **Fallback a E4B-Q6_K** (validado 540/540, ~7 GB VRAM, deja 9 GB libres)
- Documentado honestamente como "tier_16gb_safe"
- Decisión: mejor seguro que ambicioso si la calidad no cierra

---

## Tabla comparativa final (v2)

| Concepto | tier_6gb | tier_8gb | tier_10gb | tier_12gb | tier_16gb |
|---|:---:|:---:|:---:|:---:|:---:|
| **Modelo** | **E4B-IQ2_M** | **E4B-Q5_K_M** | **E4B-Q8_0** | **26B-A4B-Q3_K_XL** | **26B-A4B-IQ4_XS** |
| Familia | 4B denso | 4B denso | 4B denso | 26B MoE | 26B MoE |
| GGUF (GB disco) | 3.30 | 5.11 | 7.63 | 12.02 | 12.66 |
| VRAM cargado | 5.13 GB | 6.61 GB | 8.16 GB | ~13.5 GB | ~14.5 GB |
| % VRAM aprovechado | 85% (de 6) | 83% (de 8) | 82% (de 10) | 112% ⚠️ | 91% (de 16) |
| mmproj F16 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Context window | 8K | 16K | 16K | 8-16K (auto) | 8K |
| max_tokens | 1024 | 1280 | 1280 | 1280 | 1280 |
| Composite tools | 12 | 14 | 15 | 15 | 16 |
| Prompt tokens (~) | 1000-1200 | 1200-1400 | 1400-1500 | 1500 | 1500 |
| Vision inline auto | ❌ | ❌ | opt | ✅ | ✅ |
| MissionGoal | ❌ | ❌ | ✅ | ✅ | ✅ |
| Cadenas largas | 2-3 | 3-4 | 4-5 | 5-7 | 8+ |
| Bench Fase 2 medido | 91.6% | 91.6% | 91.6% | 93.3% | 90% + 20/20 BlqB |
| Target bench P0 v5 | ≥75% | ≥80% | ≥85% | ≥90% | ≥90% |

**Nota tier_12gb**: 13.5 GB en 12GB es **tight** (112%). Si causa OOM en hardware real, fallback a E4B-Q6_K (7.10 GB).

---

## Apéndice A: detección automática de tier

```python
# carter_v5/hardware/profile.py

def detect_tier(vram_mb: int) -> str:
    """
    Tier por VRAM. Aprovecha al máximo respetando margen 1-2 GB.

    Thresholds elegidos para que cada tier deje ~1 GB libre cuando el
    usuario tiene EXACTAMENTE esa VRAM.
    """
    if vram_mb < 5500:    return "cpu_fallback"   # Ollama qwen3:1.7b
    if vram_mb < 7500:    return "tier_6gb"       # E4B-IQ2_M (5.13 GB)
    if vram_mb < 9500:    return "tier_8gb"       # E4B-Q5_K_M (6.61 GB)
    if vram_mb < 11500:   return "tier_10gb"      # E4B-Q8_0 (8.16 GB)
    if vram_mb < 14500:   return "tier_12gb"      # 26B-A4B-Q3_K_XL (~13.5 GB)
    return                "tier_16gb"             # 26B-A4B-IQ4_XS (~14.5 GB)
```

Detección via `nvidia-smi --query-gpu=memory.total --format=csv,noheader`.

---

## Apéndice B: paths absolutos validados

```python
GEMMA_MODELS_DIR = r"C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models"

TIER_TO_PATHS = {
    "tier_6gb":  {
        "model":  f"{GEMMA_MODELS_DIR}\\E4B\\gemma-4-E4B-it-UD-IQ2_M.gguf",
        "mmproj": f"{GEMMA_MODELS_DIR}\\E4B\\mmproj-F16.gguf",
    },
    "tier_8gb":  {
        "model":  f"{GEMMA_MODELS_DIR}\\E4B\\gemma-4-E4B-it-Q5_K_M.gguf",
        "mmproj": f"{GEMMA_MODELS_DIR}\\E4B\\mmproj-F16.gguf",
    },
    "tier_10gb": {
        "model":  f"{GEMMA_MODELS_DIR}\\E4B\\gemma-4-E4B-it-Q8_0.gguf",
        "mmproj": f"{GEMMA_MODELS_DIR}\\E4B\\mmproj-F16.gguf",
    },
    "tier_12gb": {
        "model":  f"{GEMMA_MODELS_DIR}\\26B-A4B\\gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf",
        "mmproj": f"{GEMMA_MODELS_DIR}\\26B-A4B\\mmproj-F16.gguf",
        "fallback_model": f"{GEMMA_MODELS_DIR}\\E4B\\gemma-4-E4B-it-Q6_K.gguf",  # si OOM
    },
    "tier_16gb": {
        "model":  f"{GEMMA_MODELS_DIR}\\26B-A4B\\gemma-4-26B-A4B-it-UD-IQ4_XS.gguf",
        "mmproj": f"{GEMMA_MODELS_DIR}\\26B-A4B\\mmproj-F16.gguf",
        "fallback_model": f"{GEMMA_MODELS_DIR}\\E4B\\gemma-4-E4B-it-Q6_K.gguf",  # si calidad no cierra
    },
}
```

**Verificado**: todos estos archivos existen en disco al 2026-05-11.

---

## Apéndice C: VRAM medida por tier (corroborar antes de declarar)

| Tier | Modelo | VRAM medido (esperado) | VRAM real (medir) | Status |
|---|---|---|---|---|
| 6GB | E4B-IQ2_M | 5.13 GB | ⏳ pendiente | extrapolado |
| 8GB | E4B-Q5_K_M | 6.61 GB | ⏳ pendiente | extrapolado |
| 10GB | E4B-Q8_0 | 8.16 GB | ⏳ pendiente | extrapolado |
| 12GB | 26B-A4B-Q3_K_XL | 13.5 GB ⚠️ | ⏳ pendiente | extrapolado |
| **16GB** | **26B-A4B-IQ4_XS** | **14.5 GB** | **15.9 GB con ctx 8K** | **MEDIDO HOY** ✅ |

Para tier_16gb la medición real (15.9 GB) está cerca de lo extrapolado (14.5 GB) — overhead de llama-server CUDA b9090 es ~1.4 GB extra que no estaba contemplado.

**Implicación**: agregar 1.4 GB de overhead a cada estimación. Actualizar tabla:

| Tier | VRAM con overhead | ¿Cabe? |
|---|---|---|
| 6GB | 5.13 + 1.4 = 6.5 GB | ❌ NO cabe en 6GB |
| 8GB | 6.61 + 1.4 = 8.0 GB | ⚠️ Apenas en 8GB |
| 10GB | 8.16 + 1.4 = 9.6 GB | ✅ |
| 12GB | 13.5 + 1.4 = 14.9 GB | ❌ NO cabe en 12GB |
| 16GB | 14.5 + 1.4 = 15.9 GB | ✅ MEDIDO |

### Re-mapeo emergencia (si overhead es real)

| Tier | Modelo corregido | VRAM total estimado |
|---|---|---|
| 6GB | E4B-UD-IQ2_M con `-c 4096` (no 8K) | ~5.0 GB |
| 8GB | E4B-Q4_K_M (no Q5_K_M) | ~7.5 GB |
| 10GB | E4B-Q5_K_M o Q6_K con `-c 8192` | ~8.0-8.5 GB |
| 12GB | E4B-Q8_0 o 26B-A4B-UD-IQ2_M (9.33 GB) | ~10.7 GB |
| 16GB | 26B-A4B-IQ4_XS (medido) | 15.9 GB ✅ |

**Acción**: cuando arranquemos implementación, **medir VRAM real con cada modelo en hardware del usuario** antes de declarar tier final. Lo que está en Probando Gemma 4 fue con `-c 16384` siempre — bajar context cambia los números.

---

## Apéndice D: criterios de validación cross-tier

Cada tier debe pasar **ANTES de declararlo "v5 listo"**:

1. **Smoke 18 casos** (1 por categoría) en bench
2. **Bench P0 54 casos** (3 per cat × 18) — target del Doc
3. **VRAM medida** con nvidia-smi durante 5 minutos de uso
4. **Latencia p50** en 3 categorías clave (trivial, tool simple, multi-step)
5. **Calidad subjetiva**: review humano (vos) de 20 prompts representativos

**Si un tier falla en alguno**: documentamos honestamente y proponemos modelo alternativo. NO inflar números.

---

## Próximo paso (TUYO)

Leer Doc 11 + Doc 12 + Doc 13 (este).

1. ✅ "Me gusta, arrancamos" → empiezo implementación
2. ⚠️ "Ajustar X, Y, Z" → reviso antes de empezar
3. ❌ "Replantear" → vuelvo a empezar diseño

---

## Decisión crítica pendiente (necesito tu input)

**¿Validamos el modelo de cada tier con bench antes de aceptarlo?**

- **Opción A**: Bench cada tier (10 días de trabajo: ~2h bench por tier × 5 tiers + análisis + fix iterations)
- **Opción B**: Solo bench tier_16gb (lo único que vos podés validar en tu hardware), extrapolar otros tiers desde datos Fase 2 del repo
- **Opción C**: Bench tier_16gb + 1 tier representativo (tier_8gb) para confirmar que la familia E4B se comporta como esperado

**Mi recomendación**: Opción C. Te da datos en 2 puntos del espectro, suficiente para extrapolar honestamente. Cuando alguien con 6GB o 10GB quiera usar Carter, vos podés decir "te funciona X con calidad estimada Y según datos de Probando Gemma 4 + nuestro bench de validación".
