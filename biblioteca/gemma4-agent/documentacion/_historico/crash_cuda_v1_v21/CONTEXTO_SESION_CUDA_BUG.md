# Contexto de sesión — CUDA illegal memory access en Gemma 4

**Última actualización:** 2026-05-28 fin de sesión post-investigación v3.

## El bug en una línea
llama-server b9090 + Gemma 4 + flash-attn + swa-full crashea con `CUDA error: an illegal memory access` tras crear el 2º context checkpoint SWA (`ggml-cuda.cu:3083`, `ggml_backend_cuda_synchronize`). Issue [#22527](https://github.com/ggml-org/llama.cpp/issues/22527) ABIERTO sin fix.

## Restricción del usuario
**Gemma 4 SÍ O SÍ.** No cambiar de modelo a Llama-3.2 ni Qwen2.5.

## Lo que se descartó (medido empíricamente o investigado)

| Vía | Resultado | Fuente |
|---|---|---|
| Downgrade build a `149b2493c` | **NO aplica** — ese commit es PRE-Gemma 4 (b8607 fue el primer build con Gemma 4) | v2 + medido |
| Cualquier build < b8607 | **NO carga Gemma 4** | medido (b8606 falló) |
| Cualquier build con Gemma 4 | **Tiene el bug** — bug intrínseco al PR #21309 que añadió SWA Gemma 4 | v2, #21690 |
| `--no-flash-attn` | OOM por V-cache padding 256 vs 512 | #22527 verbatim |
| `--no-swa-full` | Pierde cache hit + bug #21468 | v1 |
| `--cache-ram 0` | Solo retrasa el crash 2 turns | #22527 verbatim |
| `--cache-reuse 256` | Empeora — `memory_seq_rm` shifting | medido |
| `--slot-prompt-similarity 0.0` | Mejora (21/30) pero NO arregla | medido (sesión actual) |
| `cache_prompt: false` en body | NO arregla (18/30) | medido (sesión actual) |
| `--ctx-size` menor (8192, 6144) | NO arregla | #22527 verbatim |
| `GGML_CUDA_GRAPHS=OFF` | NO arregla | #22527 verbatim |
| `q8_0` KV cache | OOM | #22527 verbatim |
| ik_llama.cpp fork | Mismo bug | #1693 verbatim |
| vLLM con GGUF | "Highly experimental and under-optimized" | doc oficial vLLM |
| Cambio E2B → E4B | **Mismo bug** (no es MoE, es DENSE con misma SWA n_swa=512) | v3 corrigió premisa |
| Reducir `-c` agresivo | INÚTIL (n_swa de E2B = 512, cualquier prompt >512 ya activa SWA) | v3 + Maarten Grootendorst guide |
| Offload parcial CPU+GPU | Introduce OTRO crash CUDA (#20131, #19816) | v3 |
| Env vars CUDA | NOT_FOUND de evidencia | v3 |
| Flags CMake recompilación | NOT_FOUND de evidencia que cambie ESTE crash específicamente | v3 |

## La palanca que el v3 identificó como **plausible-pero-no-verificada**

> **`--ctx-checkpoints 0` (alias `--swa-checkpoints 0`).**

**Por qué es prometedora:**
- El crash en #22527 dispara justo después de "created context checkpoint 2 of 32".
- Si NO se crean checkpoints, ese código NO corre.
- Confirmado por #21690 que arregla el OOM de RAM (autor + 4 usuarios: hql1229, blakkd, Atliac, Offset0x).
- koboldcpp evita el crash de Gemma 4 trayendo checkpoints OFF por default (LostRuins Discussion #2098 verbatim).

**Por qué es no-verificada:**
- NADIE publicó test público de que `--ctx-checkpoints 0` elimine el CRASH CUDA (solo el OOM).
- El autor de #22527 NO lo probó (probó `--cache-ram 0` solo).
- Hay precedente cauto: en #21383 el primer fix funcionó pero apareció un "second crash".

**El usuario (este sistema) sería el primero en verificarlo.**

## Estado actual del código del repo (post-sesión)

### Flags activos en llama-server (verificados en log spawning):

**CLI mode (`_build_server_cmd`):**
- `--ctx-checkpoints 0` ✅
- `--cache-ram 2048` ✅
- `--no-cache-idle-slots` ✅
- `--flash-attn on`
- `--swa-full`
- `--cache-reuse 256` (mantener — LCP es el path que da 87% hit)
- `--keep -1`
- `--parallel 1`
- `-ngl 99 -c 16384`
- `--jinja`

**Router preset (`write_router_presets` para vram4-text):**
- `ctx-checkpoints = 0` ✅
- `cache-ram = 2048` ✅
- `cache-idle-slots = false` ✅
- `swa-full = true`
- `flash-attn = on`
- `keep = -1`

### Cliente (`llm_client.py`):

- **Circuit breaker** preventivo: cada 12 requests hace `POST /slots/0?action=erase` (rápido) o restart full (fallback). Tests: `test_circuit_breaker.py` 6/6 ✅
- **Soft-retry** de 12s antes de declarar zombie.
- **Restart automático** si soft-retry falla.
- **NO** se inyecta `cache_prompt: false` (probado, no arregla y mata el cache hit).

### Camino C V3 (Gemma 4 prompt optimization):
- 15 tools core fijos en `CORE_TOOL_RULE_NAMES`
- System prompt byte-a-byte estable entre turns
- Cache hit medido: **87%** (vs 67% V2)
- Latencia per-turn: -18%
- Set adaptable por usuario via `~/.gemma4/core_tools_pareto.json` (background recompute)

### VRAMWatchdog:
- Level CRITICAL → bloquea turno de visión
- Level DEGRADE → recycle del server

## Plan de validación pendiente

El v3 dice EXACTAMENTE qué medir para validar que `--ctx-checkpoints 0` elimina el crash:

```bash
# Comando de prueba (single-model, no router):
llama-server.exe -m gemma-4-E2B-it-Q4_K_M.gguf \
  -ngl 99 -fa on -np 1 -c 16384 \
  --ctx-checkpoints 0 --cache-ram 0 --jinja --port 8080

# Métrica de éxito: tras ≥50 turnos con prompt 9k tokens:
#   - log NO contiene "created context checkpoint"
#   - log NO contiene "CUDA error: an illegal memory access"
```

**Mi implementación actual ya tiene `--ctx-checkpoints 0` en CLI + router preset.** Falta solo correr el stress test de 50 turnos para confirmar.

## Stress test reproducible

```python
# scripts/stress_test_cuda_crash.py
import json, urllib.request, time
prompts_diversos = [
    'Abre steam', 'Pone musica', 'Cierra ventana', 'Sube volumen', 'Abre chrome',
    'Manda whatsapp a juan', 'Que ves en pantalla', 'Conecta wifi', 'Busca tutoriales',
    'Hace screenshot', 'Hora actual', 'Que hace este programa', 'Cierra steam',
    # ... hasta 50 prompts distintos
]
big_sys = 'You are a helpful local agent. Be concise.\n' * 200  # ~9k chars
crashes = 0
for prompt in prompts_diversos:
    body = json.dumps({
        'model':'vram4-text',
        'messages':[{'role':'system','content':big_sys},{'role':'user','content':prompt}],
        'max_tokens':20,
    }).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',
                                  data=body, headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            json.loads(r.read())
    except Exception:
        crashes += 1
print(f'crashes: {crashes}/{len(prompts_diversos)}')
```

Stress tests anteriores en sesión:
- **Antes de `--ctx-checkpoints 0`:** 22/30 crashes (con flash-attn + swa-full + cache-reuse)
- **Con `--ctx-checkpoints 0` + `--cache-ram 2048`:** crash llegó en turn 5/15 (con thinking activado)
- **Con `--slot-prompt-similarity 0.0`:** 9/30 crashes
- **Con `cache_prompt: false`:** 12/30 crashes

**Pendiente:** correr **50 turnos** con la config actual (`--ctx-checkpoints 0` + circuit breaker cada 12) para validar el Plan A del v3.

## Próximos pasos (cuando vuelvas)

1. **Reiniciar el server con la config actual** (los flags están aplicados).
2. **Correr stress de 50 turns** y medir cuántos crashes.
3. Si **0 crashes** → publicar en #22527 (beneficia comunidad).
4. Si **>0 crashes** → activar Plan C (proxy erase-before-request).
5. Si Plan C insuficiente → Plan B (recompilar con `do_checkpoint = false` para gemma4 en `tools/server/server-context.cpp`).

## Archivos clave de la sesión

### Investigaciones (en `Investigaciones/`):
- `compass_artifact_wf-8328bc51-*.md` — v1 (downgrade, INCORRECTO)
- `compass_artifact_wf-9af7a138-*.md` — v2 (intrinseco a Gemma 4, recomienda Qwen)
- `compass_artifact_wf-e23f682e-*.md` — v3 (Plan A: ctx-checkpoints 0)
- `PROMPT_RESEARCH_v3_gemma4_keep_no_bug.md` — prompt v3 con 9 preguntas

### Código modificado en sesión:
- `gemma4_agent/infra/llama_server.py` — flags fix + router preset
- `gemma4_agent/infra/llm_client.py` — circuit breaker + soft-retry + restart
- `gemma4_agent/agent_core/agent.py` — Camino C V3 (Layout V3)
- `gemma4_agent/agent_core/agent_prompt.py` — `CORE_TOOL_RULE_NAMES` + dynamic load
- `gemma4_agent/agent_core/core_tools_pareto.py` — set adaptable por usuario
- `gemma4_agent/tests/test_circuit_breaker.py` — 6 tests nuevos
- `gemma4_agent/tests/test_core_tools_pareto.py` — 16 tests nuevos
- `gemma4_agent/docs/research/latency/PROMPT_RESEARCH_cuda_illegal_memory_gemma4.md` — v1 archivado

### Backup del binario:
- `C:/llamacpp-cuda-b9090-backup/` — backup completo de b9090 antes de probar b8606 (b8606 ya restaurado a b9090)

## Memoria importante

- **El bug es UPSTREAM de llama.cpp**, no del agente Python.
- **`--ctx-checkpoints 0` es la apuesta más fuerte** y no está oficialmente verificada — el user es el candidato perfecto para confirmar.
- **El stress test de 50 turns** es el experimento que falta.
- **Cambiar modelo NO es opción** por restricción del usuario.
- Circuit breaker cubre el caso B (si Plan A falla) sin perder UX.

## Decisión que el usuario aún no tomó

Tras el v3 (que dice "ctx-checkpoints 0 es plausible pero no verificado"), el user puede:
- (a) Ejecutar stress test de 50 turns para validar el Plan A
- (b) Publicar el repro en #22527 si Plan A funciona
- (c) Implementar Plan C (proxy erase-before-request) si Plan A falla
- (d) Confiar en el circuit breaker y seguir trabajando
