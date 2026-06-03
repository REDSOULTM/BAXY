# RESULTADO FINAL — Sprint v22 (Opus 4.8, 2026-05-28)

**Estado:** crash CUDA #22527 **ELIMINADO** vía flash-attn OFF + Plan A2 (system
prompt reducido). Validado con stubs + 116 unit-tests verdes. Listo para commit.
La optimización profunda de latencia de turnos de acción (FR-CoT) queda
documentada como próximo sprint (decisión del usuario: no rushearla).

---

## TL;DR

- **b9384 instalado** (con su `cudart-12.4` companion que el handoff había omitido
  — sin él el server quedaba CPU-only). **NO arregla el crash** (lo verifiqué).
- **La causa raíz NO eran los checkpoints** (ya estaban off y crasheaba igual). Es
  el **kernel flash-attn + SWA** de Gemma 4 (head sizes híbridos 512/256) en la
  transición prefill→decode, disparado por el **tamaño absoluto del prompt** (~10k+).
- **`--flash-attn off` ELIMINA el crash**: stress de 37 turnos **37/37 OK** (prompts
  hasta 20k tokens) vs **6/37** con FA on. Costo: +0.17 GB VRAM (SWA acota el KV →
  entra en 4GB) y prefill ~2× más lento en prompts grandes.
- **Plan A2** (set always-on de tool-rules 15→6) baja el piso del system prompt de
  **~9.4k → ~5.0k tokens**, devolviendo los turnos de charla/info al presupuesto y
  preservando tool-calling (**8/8 en vivo**: las reglas de los tools del subset se
  inyectan on-demand, no se pierden).
- **v21 (MAX_TOOLS=5) NO era seguro bajo uso sostenido** — su gate "6/6 OK" eran 6
  turnos cortos. En 37 turnos crasheaba igual (6/37). El cap de tools nunca fue la
  palanca; el piso del system prompt + FA sí.

---

## Qué quedó instalado / cambiado

| Componente | Antes (v21) | Ahora (v22) |
|---|---|---|
| Binario | b9260 (`3a6db741a`) | **b9384 (`48e7078ee`)** + cudart-12.4 (backup en `tools/llama-cuda.b9260-backup/`) |
| flash-attn | on | **off** (default; `GEMMA4_FLASH_ATTN=on` para A/B) |
| Set always-on tool-rules | 15 (`CORE_SIZE=15`) | **6** (`CORE_SIZE=6`; `GEMMA4_CORE_RULES=a,b,c` para override) |
| cache-ram | 0 | 0 (opt-in `GEMMA4_CACHE_RAM=<MiB>`; win modesto, cuesta RAM) |
| MAX_TOOLS | 5 | **5** (sin cambio — ver abajo) |

Archivos tocados: `infra/llama_server.py` (FA + cache-ram env-gated),
`agent_core/core_tools_pareto.py` (CORE_SIZE + default set),
`tests/test_system_prompt_scope.py` (fix de path R2). Scripts nuevos:
`_stress_v22.py`, `_verify_a2_quality.py`, `_verify_v22_defaults.py`,
`_reset_server.py`, `_kill_eval_boot_procs.py`.

---

## MAX_TOOLS

Quedó en **5**. Con FA off el crash ya no limita el cap (se podría subir), PERO
más tools = prompt más grande = prefill FA-off más lento. Dado que el objetivo
real era "que no se caiga" (logrado) y la latencia de acción ya está al límite,
no se subió. Con FR-CoT (próximo sprint) habría margen para subirlo.

---

## Latencias medidas (perfil vram4 = E2B-Q4, ctx 16K, FA off)

**Realista (low-history, = uso por voz normal):**
- Charla / info / preguntas: **0.6–3 s** ✓ en presupuesto.
- Comandos de acción (abrir app, clima): **5–16 s** — multi-call (decide→ejecutar→
  finalizar) + ejecución real (lanzar app) + prefill FA-off encima.
- Cold start (1er comando tras idle): ~14 s (carga del modelo, one-time).

**Stress worst-case (37 turnos, acumulación de historial artificial):**
| Config | p50 | p90 |
|---|---|---|
| FA-off solo | 9.3 s | 27.0 s |
| + Plan A2 | 8.0 s | 22.4 s |
| + cache-ram | 6.9 s | 19.2 s |

**Recovery:** N/A — con FA off **no hay crashes**, así que la recovery (y sus
stalls de ~30 s que rompían el flow) **nunca se dispara**. Ese era el dolor
principal del usuario y queda resuelto.

**VRAM:** ~4.1 GB total con el modelo de texto cargado (FA-off, sin visión). Entra
en el target de 4 GB. Con visión (mmproj, lazy) sube ~1.2 GB → sigue siendo
ajustado igual que en v21 (no lo empeora materialmente).

---

## CUDA crashes en la corrida de validación final

**0** (FA off, stress 37 turnos, prompts hasta 20k tokens). Confirmado en
`logs/llama-server.out.log` (el log del CHILD — NO `err.log`, que solo tiene la
vista del router; **corrección importante**: el gate del handoff grepeaba el log
equivocado).

---

## Próximos pasos (FR-CoT — el lever real de latencia de acción)

Diagnóstico medido: la multi-call YA está optimizada (el "summary pass" tras un
tool corre thinking-OFF + tools=None + 160 tok desde 2026-05-20). El costo
dominante de los turnos de acción es el **thinking de la llamada de decisión**
(p90 268 tok, max 841 @ 62 tok/s = hasta ~13.5 s), **necesario** en el E2B débil
(thinking OFF → 2/6 tool-calls medido).

El fix research-backed es **FR-CoT** (thinking estructurado breve ≤32 tok):
corta el thinking >5× **y sube** la fiabilidad (44%→64%, alucinación→0%,
arXiv 2604.02155, Qi 2026 — en `docs/research/latency/reducir_latencia_thinking_gemma4.md`).

**RIESGO conocido:** un intento previo de FR-CoT rompió media (6/6→3/6: "Gemma
emitió el formato como texto", se filtró al reply). El próximo sprint debe:
1. Implementar la plantilla FR-CoT **scopeada al canal de thinking** (que NO se
   filtre al reply visible).
2. Testear EN VIVO en TODAS las intenciones (media, apps, audio, info, charla,
   computer-use, encadenamiento) para no regresar.
3. Medir latencia (esperado: p90 de acción ~13s → ~4-6s) + calidad (gate: tool-
   calling ≥ baseline, 0 regresión en media).

Cambiar de modelo NO es opción: E4B (mejor tool-calling, menos thinking) **no
entra en 4 GB con visión**; E2B es la única opción a 4 GB (confirmado). Sí o sí
Gemma 4.

---

## Issues upstream (estado 2026-05-28)
- [#22527](https://github.com/ggml-org/llama.cpp/issues/22527) — ABIERTO, sin fix.
  Workaround nuestro = FA off (el crash vive en el kernel FA+SWA).
- [#17109](https://github.com/ggml-org/llama.cpp/issues/17109) — memory_seq_rm +
  CUDA crash. Relacionado; cache-reuse ya estaba removido por esto.

---

## Cómo revertir (si algo sale mal)
```powershell
# Binario b9384 -> b9260:
Copy-Item "tools\llama-cuda.b9260-backup\*" "tools\llama-cuda\" -Recurse -Force
# Flags v22 -> v21 (sin tocar código, vía env):
$env:GEMMA4_FLASH_ATTN = "on"      # FA on (crashea en prompts grandes)
$env:GEMMA4_CORE_RULES = "app,audio,browser,device_settings,filesystem,gui,media,session,steam,system,uia,vision,web,whatsapp,window"  # 15 rules
```
