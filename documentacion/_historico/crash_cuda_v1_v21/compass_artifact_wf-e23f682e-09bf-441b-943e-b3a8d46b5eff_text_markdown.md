# Cómo mantener Gemma 4 (gemma-4-E2B-it-Q4_K_M.gguf) en llama-server sin el crash CUDA "illegal memory access"

## TL;DR
- **El crash es intrínseco al path de SWA KV cache + context checkpoint de Gemma 4** (confirmado: issues #22527, #21690, e ik_llama.cpp #1693). NO existe a día de hoy ningún fork, PR o flag con eficacia *confirmada* que lo elimine; pero hay UNA palanca de Plan A casi sin probar y muy prometedora: **desactivar los checkpoints con `--ctx-checkpoints 0`**, porque el crash siempre dispara justo después de "created context checkpoint 2 of 32".
- **Plan A recomendado (sin recompilar):** arrancar en modo single-model con `-ctxcp 0 --cache-ram 0 -np 1 -fa on`. Si no basta → Plan C: proxy que hace `POST /slots/0?action=erase` entre turnos. Plan B (recompilar) y Plan D (circuit breaker) quedan como respaldo.
- **Reducir contexto NO sirve:** el `n_swa` de Gemma 4 E2B es **512 tokens**, así que cualquier prompt > 512 (el tuyo son ~9k) entra al path SWA igual. La única reducción útil es limitar el número de checkpoints, no el `-c`.

## Key Findings

### Estado del bug (contexto confirmado)
- **Issue #22527** ("Gemma 4 31B: illegal memory access after SWA KV cache checkpoint with Flash Attention enabled"), abierto por **Xuan-GUo el 29-abr-2026**, ABIERTO, **sin un solo comentario ni PR de fix**. Mismo hardware que tú (RTX 4060 Ti 16 GB), con CUDA 13.2 y build b8975-59237bfbb. Cita verbatim: *"The server crashes with CUDA error: an illegal memory access was encountered consistently after the second SWA KV cache context checkpoint is created… The crash occurs every time without exception, regardless of prompt content."* Crash en `ggml/src/ggml-cuda/ggml-cuda.cu:3083`, función `ggml_backend_cuda_synchronize`, justo tras "created context checkpoint 2 of 32 (pos_min = 2872, pos_max = 4407…)".
- **Issue #21690** ("Checkpoints and MMProj on Gemma 4 consume abnormal amounts of RAM"), ABIERTO. Aquí está la pista clave: el autor (en RTX 3090 24 GB, build 8724/b54cb2e) dice verbatim *"Setting '--ctx-checkpoints' to 1 or 0 with '-np 1' will prevent the server from going out of RAM."*
- **ik_llama.cpp #1693**: confirma un crash con el MISMO signature (`CUDA error: an illegal memory access … ggml_backend_cuda_synchronize`) en la bifurcación tras *"a prompt cache miss triggers KV cache eviction and recomputation"*. **Matiz importante para que verifiques bien:** ese issue es sobre el **gemma-4-26B-A4B (MoE)** en IQ4_XS, RTX 4060 Laptop 8 GB, y la línea es `ggml-cuda.cu:4059` (no 3083); además va precedido de NaN logits. Demuestra que la familia Gemma 4 arrastra el bug en el path KV/checkpoint en ambos proyectos, pero no es un repro idéntico de tu E2B.

---

### QUESTION 1 — ¿Existe fork o PATCH que lo arregle?
**Hallazgo concreto:** NO existe a día de hoy ningún PR (abierto, cerrado o merged) ni rama que arregle específicamente el illegal memory access del path SWA+checkpoint de Gemma 4. Lo relacionado y REAL:
- **PR #21309** (ngxson, "model: support gemma 4 (vision + moe, no audio)") — introdujo el soporte y con él el bug. Confirmado real.
- **PR #22288** ("server : fix swa-full logic"), **MERGED el 29-abr-2026**. Supersede al **PR #21749** ("server: ensure prompt caching for SWA models", de shipped-it). Pone `pos_min_thold = 0` cuando `--swa-full` está activo y SALTA la restauración de checkpoints — pero su objetivo es el *prompt caching* (evitar reprocesado completo), NO el crash CUDA. No hay evidencia de que cure el illegal memory access.
- **PR #22929** ("server: fix checkpoints creation", jacekpoplawski) — mueve la creación de checkpoints a fronteras de mensaje; trata el reprocesado, no el crash.
- **Forks:** koboldcpp/Nexesenex no tienen un parche dirigido al crash; koboldcpp simplemente trae checkpoints/smart-cache DESACTIVADOS por defecto (LostRuins, Discussion #2098: *"I never bothered enabling smart cache / checkpoints on KoboldCpp… On Llama-server it's enabled by default, and worse, checkpoint / and RAM cache are broken with Gemma 4"*), lo que evita el path. ik_llama.cpp tiene el bug (#1693).

**Conclusión:** no hay parche listo. La vía de Plan B habría que construirla a mano.

---

### QUESTION 2 — Variables de entorno CUDA
**Hallazgo:** NOT_FOUND de testimonios que confirmen que alguna env var CUDA elimine ESTE crash.
- `GGML_CUDA_ENABLE_UNIFIED_MEMORY`: documentado como roto en **issue #16197** (*"GGML_CUDA_ENABLE_UNIFIED_MEMORY is documented as automatically swapping out VRAM under pressure… but the problem still exists"*, RTX 3060, CUDA 13.0.1). No convierte el acceso ilegal en lento-pero-funcional; además, los foros de NVIDIA documentan que el unified memory también lanza "illegal memory access" en `cudaDeviceSynchronize`. **No recomendado.**
- `GGML_CUDA_FORCE_MMQ` / `GGML_CUDA_FORCE_CUBLAS`: no hay testimonio de que cambien este crash. En #22527 ya probaron `GGML_CUDA_GRAPHS=OFF` sin efecto.
- `CUDA_VISIBLE_DEVICES=0`: solo relevante con multi-GPU; tú tienes una sola GPU, **no aplica**.
- `CUDA_LAUNCH_BLOCKING=1`: solo debug (hace el crash más temprano/preciso, no lo evita).
- `GGML_CUDA_NO_PINNED`, `CUDA_CACHE_DISABLE=1`, `GGML_CUDA_PEER_MAX_BATCH_SIZE`: NOT_FOUND de evidencia.

**Qué probar tú (barato, ~2 min cada uno):** lanza el server con cada env var y reproduce el crash con tu prompt de 9k. ÉXITO = el server sigue respondiendo tras "created context checkpoint 2 of 32" sin imprimir "CUDA error: an illegal memory access". Coste: ~2 minutos por variable. Prioridad baja: ninguna tiene base teórica fuerte para este path.

---

### QUESTION 3 — Flags de compilación CMake
**Hallazgo:** NOT_FOUND de testimonio de que `-DGGML_CUDA_FORCE_MMQ`, `-DGGML_CUDA_F16`, `-DGGML_CUDA_DMMV_X` o `-DGGML_CUDA_MMV_Y` cambien este crash. `-DGGML_CUDA_USE_GRAPHS=OFF` ya está descartado en #22527. **No hay reporte de que la versión del CUDA Toolkit afecte este bug:** el reporter de #22527 usa CUDA 13.2 y crashea igual que tú con 12.4, así que cambiar de toolkit es poco prometedor.

**Qué probar tú (si vas a recompilar de todos modos):** compila con `-DGGML_CUDA_FORCE_MMQ=ON` y repite. Coste: una compilación (~15-40 min en tu máquina) + 5 min de test. Riesgo: solo el tiempo.

---

### QUESTION 4 — PATCH manual al código fuente
El crash vive en la lógica de checkpoint/seq_rm de la SWA KV cache. Ficheros relevantes confirmados:
- `src/llama-kv-cache-unified-iswa.cpp` (clase `llama_kv_cache_unified_iswa`, métodos `seq_rm`/`seq_cp`/`seq_add`).
- `tools/server/server-context.cpp` (cálculo de `pos_min_thold = pos_next - n_swa` y la búsqueda/creación de checkpoints).
- `ggml/src/ggml-cuda/ggml-cuda.cu` (~línea 3083, `ggml_backend_cuda_synchronize`) — aquí solo *explota* el error asíncrono; la corrupción ocurre antes, en el path KV.

**Patch más realista (el menos invasivo):** forzar que NUNCA se creen checkpoints, replicando a nivel de código lo que el flag `--ctx-checkpoints 0` hace. La lógica de PR #22288 ya demuestra que se puede SALTAR la restauración de checkpoints bajo condición; se podría extender ese guard para saltar también la *creación*. En `server-context.cpp` la creación está guardada por algo como:
```cpp
do_checkpoint = do_checkpoint && (pos_min >= 0 && slot.prompt.n_tokens() >= 64);
```
Forzar `do_checkpoint = false` para la arquitectura gemma4 evitaría el path. **Es equivalente a usar el flag, así que prueba PRIMERO el flag (Plan A) antes de tocar código.**

**Riesgo:** sin checkpoints, un cache-miss obliga a reprocesado completo del prompt (más lento), pero no rompe la corrección.

---

### QUESTION 5 — Proxy/wrapper que evita el path
**Hallazgo:** El endpoint `POST /slots/{id}?action=erase` existe y funciona en modo single-model (devuelve `{"id_slot":0,"n_erased":N}`), y NO requiere `--slot-save-path` para `erase` (sí lo requiere para `save`/`restore`). PERO hay dos avisos verificados:
- **Bug #17387:** en algunas configuraciones `action=erase` cuelga hasta Ctrl-C (verifícalo en tu build antes de depender de él).
- **Bug #18703 / #22373:** en modo router (`--models-preset`) los endpoints `/slots` devuelven 400 "Invalid action" o no están disponibles. **Si usas router mode, NO funcionará; arranca el server en modo single-model directo.**

**Estrategia del proxy:** un reverse proxy (FastAPI/aiohttp) que, antes de CADA request, haga `POST /slots/0?action=erase` para garantizar slot vacío → nunca hay match parcial → nunca se ejecuta el `memory_seq_rm` parcial que precede al checkpoint. Esto **SACRIFICA tu 87% de cache hit (Camino C)**, porque cada turno reprocesa desde cero. Por eso es Plan C, no A.

Ningún proxy existente (litellm, llama-cpp-python, ollama-proxy) trae esta capacidad "erase-before-request" de fábrica; hay que escribirla. Sketch mínimo:
```python
import aiohttp
from aiohttp import web
UPSTREAM = "http://127.0.0.1:8080"
async def handler(req):
    async with aiohttp.ClientSession() as s:
        # 1. limpia el slot 0 para evitar match parcial -> evita seq_rm parcial
        await s.post(f"{UPSTREAM}/slots/0?action=erase")
        # 2. reenvía la request original
        body = await req.read()
        async with s.post(f"{UPSTREAM}{req.rel_url}", data=body,
                          headers=req.headers) as r:
            return web.Response(body=await r.read(), status=r.status,
                                headers=r.headers)
app = web.Application(); app.router.add_route("*", "/{tail:.*}", handler)
web.run_app(app, port=9090)
```
**Riesgo:** pierdes el cache hit y subes latencia por turno (reprocesado completo). Mejora posible: solo hacer erase cuando detectes que el prompt NO comparte tu prefijo byte-estable.

---

### QUESTION 6 — ¿E4B crashea igual que E2B?
**Corrección importante de premisa:** E2B y E4B son AMBOS modelos **DENSE, NO MoE**. Solo el **26B A4B** es Mixture-of-Experts. Pasar de E2B a E4B NO cambia de dense a MoE: misma arquitectura SWA híbrida (sliding window local + global), mismo **`n_swa = 512`** para los dos modelos edge. La diferencia es solo parámetros efectivos: **E2B ~2,3B vs E4B ~4,5B** (la "E" es de "effective"/edge, no "experts").

**Implicación:** como el bug está en el path SWA+checkpoint (idéntico en E2B y E4B), E4B casi con certeza crashea igual. No encontré ningún reporte de que E4B sea estable donde E2B crashea. **NO es una vía fiable.** Además E4B Q4_K_M es más grande y aprieta más tu VRAM.

---

### QUESTION 7 — Reducir contexto agresivamente
**Dato clave confirmado:** el `n_swa` (sliding window) de Gemma 4 E2B/E4B es **512 tokens** (los 26B/31B usan 1024). Verbatim de la guía de Maarten Grootendorst: *"the smaller models (E2B and E4B) have a sliding window of 512 tokens and the larger models (26B A4B and 31B) have a sliding window of 1024 tokens."* Se ve también en el log de carga (`gemma4.attention.sliding_window`).

**Consecuencia:** tu prompt "Camino C" son ~9k tokens, MUY por encima de 512. Cualquier contexto > 512 ya activa el SWA. Bajar `-c` a 4096 o 2048 NO evita el path SWA (ya lo confirmó #22527: `-c 8192/6144/10240` crashean igual, con `-fa on -np 1 --cache-ram 0`). Para evitar SWA tendrías que caber TODO en ≤512 tokens — imposible con un prompt de 9k.

**Lo que SÍ depende del contexto es el número de CHECKPOINTS.** El crash ocurre tras "checkpoint 2 of 32". Si limitas `--ctx-checkpoints 1` (o `0`), nunca se llega al 2º checkpoint → potencialmente nunca se ejecuta el código que corrompe. **Esta es la base del Plan A.**

---

### QUESTION 8 — ¿Inferencia híbrida CPU+GPU evita el bug?
**Hallazgo:** En llama.cpp la KV cache de cada capa vive donde vive la capa. Con offload parcial (`-ngl` < total), las capas en CPU tienen su KV en CPU. En teoría, si las capas SWA quedan en CPU, el `seq_rm` correría en el backend CPU (sin acceso ilegal CUDA posible).

**PERO hay dos problemas serios:**
1. El offload parcial INTRODUCE su propio "illegal memory access" en varios reportes (#20131 con `-ngl 2`; #19816 con `-ot`). Cambiarías un crash por otro.
2. Gemma 4 E2B es minúsculo (~3,1 GB en Q4_K_M); cabe entero en tus 16 GB. Forzar capas a CPU es contraproducente en latencia y no garantiza que las capas SWA concretas queden en CPU sin `-ot` manual.

**Qué probar tú (si insistes):** usa `-ot` para fijar explícitamente las capas SWA en CPU. El layer count exacto de E2B y el patrón `is_swa` por capa hay que LEERLOS de tu log de carga (`gemma4.block_count` y las líneas `is_swa = …`) — no los inventes. Coste alto, beneficio incierto. **No es mi recomendación.**

---

### QUESTION 9 — ¿Vale la pena mandar un PR upstream?
- ggml-org/llama.cpp acepta PRs de contribuidores nuevos sin commits previos (es habitual; muchos fixes vienen de la comunidad).
- Requisitos: seguir CONTRIBUTING.md, pasar CI, y la plantilla pide "AI usage disclosure". Revisión de un code owner del área server (equipo en torno a `shipped-it`).
- Tiempo PR→merge para fixes con repro claro: típicamente de días a un par de semanas (#22288 se mergeó rápido). Un repro de #22527 + un test sería bien recibido al tratarse de un crash con un modelo oficial sin fix asignado.

---

## Details — Plan de acción ordenado

### Plan A — sin recompilar (EMPIEZA AQUÍ)
Comando de arranque sugerido (single-model, **NO router**):
```
llama-server -m gemma-4-E2B-it-Q4_K_M.gguf -ngl 99 -fa on -np 1 \
  -c 16384 --ctx-checkpoints 0 --cache-ram 0 --jinja --port 8080
```
- `--ctx-checkpoints 0` (alias `--swa-checkpoints 0`, env `LLAMA_ARG_CTX_CHECKPOINTS`): NO crear checkpoints. Es la palanca clave: el crash dispara tras crear el 2º checkpoint; sin checkpoints, ese código no corre.
- Si solo eso no basta, añade `--checkpoint-every-n-tokens -1` (alias `-cpent -1`) para asegurar que ningún checkpoint se cree durante prefill.
- **ESTADO DE EVIDENCIA (honesto y verificado por subagente):** `--ctx-checkpoints 0/1` está CONFIRMADO por varios usuarios para arreglar el problema de RAM/OOM (#21690: el autor, hql1229, blakkd, Atliac, Offset0x), pero **NADIE ha publicado un test de si elimina el CRASH CUDA**. El autor de #22527 NO lo probó (solo probó `--cache-ram 0`, que verbatim *"crash delayed by ~2 turns but still occurs"*). Es **plausible-pero-no-verificado**: el crash dispara justo después de la creación del checkpoint, así que suprimir esa creación *debería* evitar el path — pero el caso análogo #21383 (donde `--cache-ram 0` previno el primer crash pero apareció *"a second crash"*) obliga a ser cauto. Eres el candidato perfecto para confirmarlo.
- **Cómo medir éxito:** reproduce tu flujo de ≥3 turnos (idealmente 50) con el prompt de 9k. ÉXITO = en el log NO aparece "created context checkpoint" y el server NO imprime "CUDA error: an illegal memory access" tras varios turnos. Coste de la prueba: ~5 minutos.

### Plan B — recompilar binario propio
Si Plan A falla, recompila forzando `do_checkpoint = false` para gemma4 en `tools/server/server-context.cpp` (ver Q4), o prueba `-DGGML_CUDA_FORCE_MMQ=ON`. Coste: 1 compilación. Manda el repro a #22527 de paso.

### Plan C — proxy con erase-before-request
Si necesitas checkpoints por rendimiento y aun así crashea, mete el proxy de la Q5. Sacrificas cache hit pero garantizas no-crash (modo single-model obligatorio por #18703; vigila el cuelgue de #17387).

### Plan D — convivir con el circuit breaker
Ya lo tienes. Si A/B/C no convencen, mantén el circuit breaker cada 12 requests + soft-retry, y añade un `erase` programático en el catch del crash.

## Recommendations
1. **HOY:** prueba Plan A (`--ctx-checkpoints 0 --cache-ram 0 -np 1 -fa on`) y mide con los log lines exactos. Son 5 minutos y es la hipótesis con mayor probabilidad de éxito.
2. Si funciona, **publícalo en #22527** (beneficia a la comunidad y te valida el hallazgo). **Umbral de decisión:** si tras 50 turnos no aparece "CUDA error", considéralo resuelto a <1% incidencia.
3. Si NO funciona, salta a **Plan C** (proxy erase) — garantiza no-crash a costa de latencia. **Umbral:** si la latencia por turno supera ~2× tu baseline, pasa a **Plan B** (recompilar sin checkpoints, que conserva el cache LCP del prefijo byte-estable).
4. **NO inviertas en:** cambiar de E2B a E4B (mismo bug, misma arquitectura dense + SWA), reducir `-c` (n_swa=512 lo hace inútil), env vars CUDA (sin evidencia), ni offload parcial (introduce otro crash).

## Caveats
- La eficacia de `--ctx-checkpoints 0` contra el **CRASH** (no contra la RAM) es **plausible pero NO confirmada** por ningún test público; podrías ser el primero en verificarlo. No lo presentes como hecho hasta medirlo.
- `--cache-ram 0` por sí solo está **DESCARTADO** como solución (solo retrasa el crash ~2 turnos, según el autor de #22527); lo incluyo en el comando A solo como refuerzo, no como fix.
- El endpoint `/slots ?action=erase` puede colgarse (#17387) y NO funciona en router mode (#18703); usa single-model.
- koboldcpp evita el crash por traer checkpoints OFF por defecto, pero es OTRO binario (no `llama-server`), por lo que no satisface tu requisito de usar llama-server; lo menciono solo como confirmación de la hipótesis "sin checkpoints, no crash".
- ik_llama.cpp #1693 es sobre el **26B A4B (MoE)** con NaN logits y línea `cu:4059`, no un repro idéntico de tu E2B; úsalo como evidencia de patrón, no como caso exacto.
- El layer count y el patrón `is_swa` exactos de E2B deben leerse de TU log de carga, no asumirse.
- No pude verificar la cadena exacta del env var de `--checkpoint-every-n-tokens`; usa el flag en línea de comandos (`-cpent -1`) para evitar ambigüedad.