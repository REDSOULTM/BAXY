# 04 — De las carpetas de investigaciones (ambas)

Resumen de lo extraído de los .md de investigación (no el código), cruzado con
lo que ya aplicamos en los 8 informes + ducking.

## Carpeta del proyecto actual (`gemma4_agent/docs/research/`)

Es **nuestra propia** investigación. Ya está minada — es la fuente de los commits
recientes. Confirmado al leer:
- `agent_arquitectura/informe_abcd_...` y `router_chain_foco_windows_carter_...`
  (ambos 2026-05-23) → son el origen del router-gate, chaining, foco Windows y
  sampling que aplicamos. **Nada nuevo sin aplicar de impacto.**
- `latency/`, `voice_stt/`, `router/`, `streaming/` → ya reflejados en el código
  (Parakeet, cache-reuse, router rebuild, streaming profile).

**Único pendiente menor detectado:** `latency/` menciona persistir KV con
`--slot-save-path` + `/slots/0/save|restore` para reuso ENTRE sesiones, y
keep-alive cada 30s. No lo aplicamos. ROI: arranque más rápido en la 2ª sesión.
Bajo riesgo. Candidato menor.

## Carpeta de Carter (`Carter OS AI/docs/investigaciones/`, 57 .md)

Los dossiers Opus (`investigacionesopus/`) y patterns (`audit_qwen3/`) son la
investigación técnica más densa. Cruzados con lo nuestro:

| Dossier Carter | Tema | ¿Aporta sobre lo nuestro? |
|---|---|---|
| `04_Agent_loop_21_fails` | planner-light + skill library + error classifier + loop v2 | **SÍ**: error classifier (cand. 2), skill library (cand. en 03), no_progress (cand. 3). Lo demás ya lo tenemos. |
| `05_GUI_universal_CEF` | Chromium a11y flag + cascading UIA | **SÍ**: cand. 4. |
| `audit_qwen3/14_PATRONES_A_P` | 60 fails clasificados en patrones A-P | **SÍ parcial**: allow-list deeplinks (A, cand. 5), few-shot anti-overuse (D), destructive pre+post LLM (F, ya lo hacemos con email-gate). Muchos son bench-bugs de Carter, no nuestros. |
| `02_Gemma4_E2B_E4B_eval` | evaluación de quants | Confirma E4B; ya validado por nosotros. |
| `03_Opt_qwen3_ultimo_10%` | tuning Qwen3/Ollama | **NO** — es Qwen3/Ollama (v1-v3), no aplica a Gemma4/llama.cpp. |
| `06_Dual_LLM_vs_Single` | perfiles VRAM | Confirma single-LLM (ya decidido). |
| `07_Skills_MCP` | skills + MCP | Tenemos skills_registry; MCP es opcional futuro. |
| `La razon de carter/*` | tesis/competidores/producto | **NO técnico** — descartado para esta auditoría. |

## Patrones A-P de Carter cruzados con bugs reales NUESTROS

Algunos patterns de Carter describen bugs que TAMBIÉN tuvimos o podríamos tener:

- **Pattern A (URIs inventadas)** → nuestro candidato 5 (allow-list deeplinks).
- **Pattern B (retrieval anafórico falla en queries cortas)** → es justo lo que
  nuestro context_router multilingüe + RRF del router ataca. Validación cruzada.
- **Pattern D (few-shot induce tool-overuse: "qué hora es"→tool sobre "qué es X")**
  → nuestro intent_router (info-vs-acción semántico) ya lo separa. Confirmar con
  "qué es Python" que NO dispare tool.
- **Pattern F (intención destructiva pre+post LLM)** → tenemos email-gate +
  safety.classify_tool_call. Carter sugiere TAMBIÉN chequear `tool_args` post-LLM
  (no solo el texto del user). **Posible mejora menor**: espejar el check sobre
  los args que el modelo realmente eligió.
- **Pattern E (empty reply de modelos 4B)** → tenemos forced-retry. Carter agrega
  "detector de ambigüedad pre-LLM → clarificador canned". Menor.

## Síntesis de las investigaciones

La investigación de Carter **no contradice** ninguna decisión nuestra; la refuerza
y agrega ~5 features concretas (ver 03). Lo más accionable de las investigaciones
(no del código) son: **error classifier, allow-list deeplinks, Chromium a11y flag,
y el check destructivo post-LLM sobre args**. Todo lo demás o ya lo tenemos, o es
específico de Qwen3/Ollama, o es producto/tesis.
