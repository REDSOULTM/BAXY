# Sprint — Recompilar llama.cpp con parche local SWA (Gemma 4 CUDA #22527)

**Autor:** Claude Opus 4.7 — 2026-05-28
**Estado:** PLAN INVESTIGADO (no ejecutado). Listo para correr cuando el dev decida.
**Objetivo:** Eliminar el bug CUDA #22527 en raíz, no enmascararlo con cap de tools.
**Restricción:** Gemma 4 SÍ O SÍ (no cambiar modelo).

> **CORRECCIÓN respecto a la v0 del sprint:** mi hipótesis previa decía que
> koboldcpp tiene `do_checkpoint=false` por default. **Eso es incorrecto** —
> verificado en [koboldcpp Discussion #2098](https://github.com/LostRuins/koboldcpp/discussions/2098):
> SerialKicked identificó que el problema en llama.cpp es el **cache RAM**
> y los **context checkpoints**, no algo del path CUDA mismo. koboldcpp evita
> el bug porque no usa esa feature, no porque la parchee.
> Esto cambia la estrategia: nuestro parche debe **saltar el `create_checkpoint`
> para arch híbridas Gemma 4** (no es un fix CUDA, es no entrar al path
> culpable).

---

## Por qué este sprint

Workarounds aplicados (v17–v20) reducen frecuencia pero NO eliminan el bug:

| Versión | Crashes/6 turnos | Estado |
|---|---|---|
| Config 27-may sin Plan A | 5/6 | inestable |
| Plan A (`ctx-checkpoints=0` + `cache-ram=0`) | 4/6 visible, 2 enmascarados | inestable |
| Plan A + recovery v18 (3 restart bucle) | 0/6 visible (2 silenciados) | aceptable |
| **Plan A + recovery v18 + hard cap 5 tools (v20)** | **0/6 + 0 crashes en child PID 2686** | **excelente (prompts <12k toks)** |

**v20 es el estado actual en prod.** Funciona porque mantiene los prompts bajo
~12k tokens — el umbral donde el bug se dispara. Pero:

- Si un turn requiere **≥6 tools simultáneas** (computer_use complejo) → no
  alcanza el subset.
- Si un microagent crece (memoria persistente, project context grande) →
  prompt vuelve a >13k → crash visible.

**Plan #1 ataca la raíz:** parchar el binario para que el bug nunca se dispare.

---

## El bug en detalle (lo que SABEMOS por código + issues)

### Causa raíz (confirmada en #21468 + #22527 + análisis de PawelHuryn)

Gemma 4 tiene **arquitectura híbrida**:
1. **Mezcla de layers SWA y full-attention.** Las layers no-SWA usan
   `n_embd_head_k = 512`; las SWA usan `n_embd_head_k_swa = 256`. **Mismatch
   de tamaños** entre layers.
2. **Shared KV Cache:** las últimas `num_kv_shared_layers` reusan K/V del
   último layer no-shared del mismo tipo (SWA o full).

Cuando llama-server crea un **context checkpoint SWA** (función
`create_checkpoint`), llama a `llama_state_seq_get_data_ext(...)` con
`LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY`. Este path, con **flash-attn activo**
sobre el modelo híbrido, genera un **access pattern inválido en CUDA** porque
las assumptions del kernel no manejan el mismatch de head sizes entre layers.

### Stack trace exacto (de #22527)

- Archivo: `ggml/src/ggml-cuda/ggml-cuda.cu:3083`
- Función: `ggml_backend_cuda_synchronize` → `cudaStreamSynchronize(cuda_ctx->stream())`
- Trigger: justo después de "created context checkpoint 2 of 32" en el log.

### Callsite en código

- Archivo: **`tools/server/server-context.cpp`**
- Función `create_checkpoint` en línea **1968–1990**.
- Llamada desde **`update_slots()`** alrededor de líneas **2400–2430**.
- Las llamadas problemáticas dentro de `create_checkpoint`:
  ```cpp
  cur.update_tgt(ctx_tgt, slot.id, LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY);
  cur.update_dft(ctx_dft.get(), slot.id, LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY);
  ```

### Issues upstream relacionados

- **#22527** ABIERTO (29-abr-2026) — el bug exacto. Reporter: Xuan-GUo. Build
  reportado: b8975. SIN respuesta de maintainers, SIN PR linkeado al 28-may-2026.
- **#21468** — cache-reuse no soportado para Gemma 4. ARREGLADO por
  **PR #22288** (mergeado 24-abr-2026 en master, commit `ffdd983`). Incluido
  en build b9090.
- **#21690** — checkpoints + mmproj consumen RAM abnormal en Gemma 4. ABIERTO.
  Reporter: SerialKicked (9-abr-2026). Workaround: `--ctx-checkpoints 0|1 -np 1`.
- **#17109** — `memory_seq_rm` + decode crashea con CUDA. CERRADO como stale
  sin fix (bug-unconfirmed).
- **PR #15293** — introdujo SWA checkpoints (mergeado 14-ago-2025, autor:
  ggerganov). Es de aquí que viene el código culpable.

### Build actual

- **b9090** = commit `5757c4dcb178a01c85234a6db7503b19c9598873` (9-may-2026,
  solo update de BoringSSL — no toca el bug).
- master al 28-may-2026: tags hasta b9384. Ninguna release intermedia menciona
  "Gemma" / "checkpoint" / "CUDA" en sus títulos. **Mi parche tiene que ser local.**

---

## El parche (estrategia validada)

### Lógica del parche

Saltar la creación del checkpoint cuando el modelo tiene la combinación
"híbrida con head size mismatch". El check correcto NO es por arch name
(LLM_ARCH_GEMMA3) — eso es frágil porque los arches cambian. El check correcto
es **estructural**: si el modelo tiene `n_swa > 0` Y `flash_attn=on` Y hay
**mismatch entre `n_embd_head_k` y `n_embd_head_k_swa`** → skip checkpoint.

### Pseudocódigo del parche

```cpp
// tools/server/server-context.cpp, dentro de create_checkpoint (~línea 1968)
void create_checkpoint(server_slot & slot, const int64_t n_tokens_cur,
                       llama_pos pos_min, llama_pos pos_max) {
    // v17-patch (Probando Gemma 4 sprint, 2026-05-XX): skip checkpoints
    // on hybrid SWA models with flash-attn. Workaround for
    // https://github.com/ggml-org/llama.cpp/issues/22527
    // (CUDA illegal memory access in ggml-cuda.cu:3083 triggered by
    // create_checkpoint -> update_tgt -> llama_state_seq_get_data_ext
    // when the model has mismatched head sizes between SWA and non-SWA
    // layers, which is the case for all Gemma 4 variants).
    //
    // Detection is structural (not arch name): n_swa > 0 AND flash_attn
    // active AND the model exhibits the head size mismatch.
    const llama_model * model = llama_get_model(ctx_tgt);
    const bool is_swa = llama_model_n_swa(model) > 0;
    const bool has_fa = params_base.flash_attn != GGML_FLASH_ATTN_TYPE_DISABLED;
    // n_embd_head_k vs n_embd_head_k_swa mismatch detection:
    // need to query the model for both. Exact API call depends on
    // llama.h version — for b9090 it's llama_model_n_embd_head_k() and
    // llama_model_n_embd_head_k_swa() (verify these exist).
    if (is_swa && has_fa) {
        SLT_INF(slot, "skipping context checkpoint (Gemma 4 SWA+FA workaround #22527)\n");
        return;
    }
    // ... resto del código original ...
}
```

### Alternativa más conservadora (recomendada si la detección estructural falla)

Si los hooks `n_embd_head_k_swa` no existen en la API de b9090, usar un check
por arch name explícito:

```cpp
const llama_model * model = llama_get_model(ctx_tgt);
const llm_arch arch = llama_model_get_arch(model);  // verificar API exacta
if (arch == LLM_ARCH_GEMMA3 ||  // E2B/E4B
    arch == LLM_ARCH_GEMMA3N || // n-variants
    /* añadir GEMMA4 si existe */) {
    SLT_INF(slot, "skipping context checkpoint (Gemma SWA workaround #22527)\n");
    return;
}
```

**Trade-off:** la versión arch-aware es más fácil de implementar pero requiere
mantener la lista de arches cuando aparezcan modelos nuevos. La versión
estructural es más robusta pero requiere identificar los hooks correctos
de la API.

---

## Toolchain auditado (este sistema, verificado 2026-05-28)

| Componente | Estado | Detalle |
|---|---|---|
| CUDA toolkit | ✅ | 13.0.88 en `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0` |
| CUDA + VS integration | ✅ | `extras/visual_studio_integration/` presente |
| GPU | ✅ | RTX 4060 Ti 16 GB, driver 596.36 (compute capability **89**, Ada Lovelace) |
| CMake | ✅ | 4.2.1 |
| Visual Studio 2022 Build Tools | ✅ | en `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools` |
| MSVC `cl.exe` | ✅ | `14.44.35207\bin\Hostx64\x64\cl.exe` (NO está en PATH; usar `vcvars64.bat`) |
| Git | ✅ | 2.50 |
| Ninja | ❌ | **NO instalado**. Alternativas: instalar (`scoop install ninja` o `choco install ninja`) o usar el generator MSVC nativo (más lento pero funciona). |
| Disco libre | ✅ | 168.9 GB en C: |

**Conclusión:** todo listo salvo Ninja (opcional). El path de fallback es
`cmake -G "Visual Studio 17 2022"` directamente con MSBuild.

---

## Pasos del sprint (orden de ejecución)

### Paso 1 — Preparación (15 min)

```powershell
# Instalar ninja (opcional, recomendado por velocidad de build)
winget install Ninja-build.Ninja
# o: scoop install ninja
# o: choco install ninja

# Clonar al lado del repo del proyecto (NO dentro)
cd C:\Users\usuario\Desktop\ETC\Programacion
git clone https://github.com/ggml-org/llama.cpp llama.cpp-fork
cd llama.cpp-fork
git checkout 5757c4dcb178a01c85234a6db7503b19c9598873  # tag b9090

# Verificar archivos del bug
Test-Path tools/server/server-context.cpp  # debe ser True
```

### Paso 2 — Identificar el callsite real en el código de b9090 (15 min)

El número de línea exacto (1968) viene de master al 28-may-2026. En b9090
puede ser distinto. Verificar antes de patchar:

```powershell
# Buscar la funcion en server-context.cpp
Select-String -Path "tools/server/server-context.cpp" -Pattern "void create_checkpoint|create_checkpoint\(" | Select-Object -First 5

# Verificar API disponible para n_embd_head_k_swa
Select-String -Path "include/llama.h","src/llama-model.cpp" -Pattern "n_embd_head_k_swa|n_embd_head_k\b|llama_model_n_swa" | Select-Object -First 20
```

**Decisión:** si `llama_model_n_embd_head_k_swa()` NO existe en la API
pública → usar el path arch-aware (más simple).

### Paso 3 — Aplicar el parche (15 min)

Editar `tools/server/server-context.cpp` con el guard al inicio de
`create_checkpoint`. Hacer un commit local con mensaje claro:

```powershell
git add tools/server/server-context.cpp
git commit -m "WORKAROUND: skip SWA checkpoint for Gemma 4 (issue #22527)"
```

### Paso 4 — Configurar el build CUDA (15 min)

```powershell
# Abrir Developer PowerShell de VS2022 (o ejecutar vcvars64.bat)
& "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

# Configurar build
cd C:\Users\usuario\Desktop\ETC\Programacion\llama.cpp-fork

# Variant A — con ninja (recomendado, ~10 min total):
cmake -B build -G "Ninja" `
    -DGGML_CUDA=ON `
    -DCMAKE_BUILD_TYPE=Release `
    -DCMAKE_CUDA_ARCHITECTURES=89 `
    -DGGML_NATIVE=ON `
    -DGGML_CUDA_FA=ON `
    -DGGML_CUDA_F16=ON

# Variant B — con Visual Studio generator (fallback si ninja falla):
cmake -B build -G "Visual Studio 17 2022" -A x64 `
    -DGGML_CUDA=ON `
    -DCMAKE_CUDA_ARCHITECTURES=89 `
    -DGGML_NATIVE=ON
```

### Paso 5 — Compilar SOLO llama-server (30–60 min)

```powershell
# Build target específico (no todo el monorepo, ahorra ~30 min)
cmake --build build --target llama-server --config Release -j 8

# El binario queda en: build/bin/Release/llama-server.exe
# o build/bin/llama-server.exe (depende del generator)
```

**Estimación:** 30 min con ninja en RTX 4060 Ti, 60 min con VS generator.

### Paso 6 — Swap del binario (5 min)

```powershell
cd C:\Users\usuario\Desktop\ETC\Programacion\"Probando Gemma 4"

# Backup del binario original (CRITICAL — para rollback rápido)
Copy-Item tools/llama-cuda/llama-server.exe tools/llama-cuda/llama-server.exe.b9090-original -Force

# Instalar el patched
Copy-Item ..\llama.cpp-fork\build\bin\Release\llama-server.exe tools/llama-cuda/llama-server.exe -Force
```

### Paso 7 — Smoke test (10 min)

```powershell
# Subir el hard cap a 8 para STRESSAR el bug que el v20 enmascaraba
$env:GEMMA4_HARD_TOOL_CAP = "8"
$env:GEMMA4_MAX_SELECTED_TOOLS = "8"

# Limpiar logs viejos para que cualquier crash sea de ESTA corrida
Remove-Item gemma4_agent/logs/llama-server.*.log -ErrorAction SilentlyContinue

# Arrancar server
python scripts/_kill_server_ports.py
python scripts/_boot_server_for_eval.py

# Probe: los 6 turns que ya conocemos (turns 2 y 4 cruzaban 13.6k toks
# antes y disparaban CUDA #22527)
python scripts/_revert_live_probe.py
```

**Gate:**
- 6/6 OK en el probe.
- `Select-String -Path gemma4_agent/logs/llama-server.err.log -Pattern "CUDA error"` debe devolver **0 matches**.
- Mensaje "skipping context checkpoint" debe aparecer en el log (confirmación de que el parche está activo).

### Paso 8 — Stress test (30 min)

```powershell
python scripts/stress_test_cuda_crash.py
```

**Gate:** 0 CUDA errors en 50 iteraciones con prompts variables.

### Paso 9 — Validación de cache hit (10 min)

El parche desactiva los SWA checkpoints. Esto puede **degradar el prefix-cache
hit rate**. Medir:

```powershell
# Después del probe, contar cuántos turns reprocesaron el prompt completo
Select-String -Path gemma4_agent/logs/llama-server.out.log -Pattern "n_tokens = 0, memory_seq_rm \[0, end\)" | Measure-Object | Select-Object -ExpandProperty Count
```

**Gate:** ≤1 "full reprocess" por probe de 6 turns (sin parche debería ser 0
con cache-reuse + swa-full; con parche puede llegar a 1–2, aceptable).

Si el cache hit se degrada >50%, considerar **alternativa #2**: parchar
`create_checkpoint` para que devuelva success pero NO haga el `update_tgt`
(en vez de skip total). Esto preserva la lista de "checkpoints existentes"
para el path de `find_better_prompt` aunque cada checkpoint sea no-op.

### Paso 10 — Si pasa los gates, producción (10 min)

```powershell
# Restaurar MAX_TOOLS a 8 permanentemente
# (editar gemma4_agent/routing/planner.py:22 → MAX_SELECTED_TOOLS = 8)
# (editar gemma4_agent/agent_core/agent.py:1665 → _hard_cap = 8)

# Documentar el parche
git -C ..\llama.cpp-fork format-patch HEAD~1 -o ../"Probando Gemma 4"/documentacion/patches/

# Commit en el repo del proyecto
git add documentacion/patches/*.patch
git commit -m "feat: integrar binario llama.cpp parcheado para CUDA #22527"
```

### Paso 11 — Si NO pasa los gates

Posibilidades en orden de probabilidad:

1. **El parche compila pero el crash persiste.** Significa que el path
   problemático NO es solo `create_checkpoint`. Hay que extender el guard a
   `find_better_prompt` y al restore desde checkpoint (PR #22384 menciona
   bugs en restore para modelos híbridos). Revisar `prompt_load` /
   `find_better_prompt` en el mismo archivo.

2. **El parche revienta el cache hit.** Aplicar la "alternativa #2" del Paso 9.

3. **La API `llama_model_n_embd_head_k_swa` no existe.** Usar el path
   arch-aware con `LLM_ARCH_GEMMA3` / `LLM_ARCH_GEMMA3N`.

4. **El build CUDA falla.** Causas más comunes:
   - `cl.exe` no en PATH → ejecutar `vcvars64.bat` primero.
   - `nvcc` no encuentra `cudart` → verificar `CUDA_PATH` env var.
   - VS integration de CUDA no detectada → reinstalar CUDA toolkit con
     opción "Visual Studio integration" marcada.

---

## Plan de rollback (instantáneo)

```powershell
cd C:\Users\usuario\Desktop\ETC\Programacion\"Probando Gemma 4"
Copy-Item tools/llama-cuda/llama-server.exe.b9090-original tools/llama-cuda/llama-server.exe -Force
python scripts/_kill_server_ports.py
python scripts/_boot_server_for_eval.py
```

Vuelve al estado v20 (hard cap 5 + recovery v18) en <1 minuto.

---

## Estimación total

| Fase | Tiempo optimista | Tiempo pesimista |
|---|---|---|
| Preparación + clone + checkout | 15 min | 30 min |
| Identificar callsite + decidir API | 15 min | 60 min |
| Aplicar parche + commit local | 15 min | 30 min |
| Configure cmake | 15 min | 30 min |
| Build llama-server | 30 min | 90 min (sin ninja) |
| Smoke + stress + cache-hit gates | 60 min | 120 min |
| **TOTAL** | **2.5 h** | **6 h** |

Disco: ~3 GB para clone + build artifacts.
Riesgo: si la primera estrategia falla, +2–4 h iterando alternativas.

---

## Riesgos identificados

1. **El parche es estructural pero el bug puede tener más callsites.** Si
   `find_better_prompt` también dispara el path culpable (probable según
   #22384), el parche solo mueve el problema. Mitigación: el Paso 11.1
   cubre este caso.

2. **Cache hit se degrada.** El parche desactiva los SWA checkpoints que
   son el optimization que da ~13x speedup en cache-reuse. Sin ellos, cada
   turn nuevo puede reprocesar el prompt entero (~6s prefill en E2B-Q4).
   Mitigación: medir en el Paso 9; aplicar alternativa #2 si pasa de 50%.

3. **Builds Windows + CUDA son frágiles.** Errores conocidos:
   `nvcc fatal: Don't know what to do with...` (CUDA-MSVC mismatch),
   `LNK1181 cannot open input file 'cudart.lib'` (PATH), `cl.exe: too many
   arguments` (línea de comando >32k chars en builds grandes; solo el
   target llama-server evita esto).

4. **Régression en otros modelos.** El parche aplica SOLO a modelos con
   `n_swa > 0 + flash_attn + head mismatch` — Gemma 4 entra, otros como
   Llama/Mistral no (no tienen el mismatch). Aún así, conviene probar el
   binario parcheado con un modelo no-SWA (ej. Qwen 2.5) para confirmar
   que no rompió nada.

5. **Falta de GPU CI.** Solo se puede medir en la máquina del dev. Cualquier
   regresión se detecta en vivo. Mitigación: tener el backup `.b9090-original`
   listo para rollback (<1 min).

6. **El bug puede tener fix oficial entre el sprint y prod.** Antes de
   correr el sprint, revisar últimos commits en master:
   ```powershell
   git -C ..\llama.cpp-fork log --oneline master --grep="22527\|SWA\|Gemma\|checkpoint" -20
   ```
   Si hay un fix oficial, mejor rebase + usar build oficial.

---

## Decisión: cuándo correr el sprint

**No es urgente.** El estado v20 actual da 0 crashes visibles en 6/6 turns
con child estable. El sprint vale la pena cuando:

- ✅ Un turn real requiera ≥6 tools y el subset cap nos limite.
- ✅ Aparezca un fix oficial upstream y queramos integrarlo.
- ✅ El dev tenga 4h libres y quiera eliminar la deuda técnica de v20.

**No vale la pena correr el sprint si:**

- ❌ v20 sigue cubriendo todos los casos de uso del usuario por semanas.
- ❌ Aparecen problemas más urgentes que invierten la prioridad.

---

## Fuentes citadas (todas verificadas 2026-05-28)

1. [llama.cpp issue #22527 — Gemma 4 CUDA crash](https://github.com/ggml-org/llama.cpp/issues/22527) — el bug exacto, ABIERTO sin fix.
2. [llama.cpp issue #21468 — cache reuse for Gemma 4](https://github.com/ggml-org/llama.cpp/issues/21468) — arreglado por PR #22288, INCLUIDO en b9090.
3. [llama.cpp issue #21690 — checkpoints OOM RAM en Gemma 4](https://github.com/ggml-org/llama.cpp/issues/21690) — ABIERTO, workaround `--ctx-checkpoints 0|1`.
4. [llama.cpp issue #17109 — memory_seq_rm + decode CUDA crash](https://github.com/ggml-org/llama.cpp/issues/17109) — CERRADO como stale.
5. [llama.cpp PR #15293 — server: add SWA checkpoints](https://github.com/ggml-org/llama.cpp/pull/15293) — introdujo el código culpable (ggerganov, 14-ago-2025).
6. [llama.cpp PR #22288 — fix swa-full logic](https://github.com/ggml-org/llama.cpp/pull/22288) — mergeado 24-abr-2026, commit `ffdd983`, incluido en b9090.
7. [llama.cpp release b9090](https://github.com/ggml-org/llama.cpp/releases/tag/b9090) — commit `5757c4dcb178a01c85234a6db7503b19c9598873`, 9-may-2026.
8. [llama.cpp tools/server/server-context.cpp master](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/server-context.cpp) — código del bug en función `create_checkpoint` líneas 1968–1990.
9. [llama.cpp common/arg.cpp master](https://github.com/ggml-org/llama.cpp/blob/master/common/arg.cpp) — declaración de los flags `--ctx-checkpoints`, `--cache-ram`, `--no-cache-idle-slots`, `--checkpoint-min-step`.
10. [koboldcpp Discussion #2098 — Gemma4 SWA en kcpp vs llama.cpp](https://github.com/LostRuins/koboldcpp/discussions/2098) — SerialKicked identifica checkpoints + RAM cache como culpables; CORRIGE mi hipótesis previa.
11. [Paweł Huryn — Gemma 4 shared KV cache architecture](https://x.com/PawelHuryn/status/2042276953470931197) — explicación de la arch híbrida que rompe assumptions de llama.cpp.
12. [Gemma 4 architecture explainer (Botmonster)](https://botmonster.com/posts/gemma-4-architecture-per-layer-embeddings-shared-kv-cache-dual-rope/) — detalles de Shared KV Cache y per-layer embeddings.

---

## Apéndice — Estado del sistema al cierre de la investigación

- v20 corriendo en prod (server PID variable, child PID 2686 estable al
  momento de la última medición).
- `MAX_SELECTED_TOOLS=5`, `GEMMA4_HARD_TOOL_CAP=5`, `GEMMA4_ZOMBIE_RECOVERY_ATTEMPTS=3`.
- 6/6 OK live probe, 0 CUDA errors en child actual.
- Prompts máx medidos: 11.7k tokens (vs umbral de crash ~13k).
- Recovery v18 (bucle de 3 restarts) listo para silenciar cualquier crash
  residual si v20 falla en un caso edge.
