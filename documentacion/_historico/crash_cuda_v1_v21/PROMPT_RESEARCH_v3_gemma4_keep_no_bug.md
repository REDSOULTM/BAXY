# Investigación v3 — Mantener Gemma 4 y eliminar el bug CUDA "illegal memory access"

## Estado tras investigaciones v1 + v2

Las v1 y v2 concluyeron:
- **v1 (incorrecta):** "downgrade a `149b2493c`" → falso, ese commit es PRE-Gemma 4.
- **v2 (corrige v1):** el bug es **intrínseco a la implementación SWA del modelo Gemma 4** (PR #21309 de ngxson, b8607). Nació con el soporte del modelo. **Toda versión que cargue Gemma 4 tiene el bug.**
- **v2 recomienda:** migrar a Qwen2.5-3B-Instruct (sin SWA).

**Restricción del usuario:** SÍ O SÍ Gemma 4. No se cambia de modelo.

Esto deja **3 vías inexploradas** que ni v1 ni v2 cubrieron:

1. **Workaround a nivel de runtime (kernel/CUDA env vars)** que las v1/v2 no exploraron a fondo.
2. **Patch local del binario llama.cpp** (recompilar con un parche puntual al path culpable).
3. **Wrappers/proxies a llama-server** que reescriban el request antes de que llegue al binario buggy.

Este prompt focaliza el research en **mantener Gemma 4 funcional sin el crash**.

---

## Prompt para Claude.ai (v3)

```
Necesito investigar EXCLUSIVAMENTE soluciones que MANTENGAN el modelo Gemma 4
funcionando con llama-server. Las investigaciones previas concluyeron que
el bug CUDA "illegal memory access" en SWA KV cache + checkpoint es intrínseco
a la implementación de Gemma 4 (PR #21309 de ngxson, llegó con el soporte
inicial del modelo en b8607). Cambiar de modelo NO es opción.

Lo que YA sé y validé empíricamente (no me lo repitas):
- Build b9090 actual tiene el bug. Crash en ggml_backend_cuda_synchronize
  línea 3084 (ggml-cuda.cu) tras memory_seq_rm en el path SWA.
- Issues #22527 (Gemma 4) y #21690 (checkpoints "consistent since initial
  implementation") están ABIERTOS sin PR de fix.
- ik_llama.cpp también tiene el bug con Gemma 4 (issue #1693).
- Flags --flash-attn off, --cache-ram 0, --ctx-size pequeño, GGML_CUDA_GRAPHS=OFF,
  q8_0 KV: NINGUNO arregla (confirmado en #22527).
- Probé b8606 → NO carga Gemma 4 (modelo añadido en b8607).
- Hardware: RTX 4060 Ti 16 GB, Compute 8.9, CUDA 12.4, Windows 11.
- Modelo: gemma-4-E2B-it-Q4_K_M.gguf (~3.1 GB).
- Mi cliente Python ya tiene: circuit breaker cada 12 requests, soft-retry,
  Camino C (prompt estable byte-a-byte) con cache hit 87%.

Lo que NECESITO que investigues a fondo (cosas que las v1/v2 NO cubrieron):

### Pregunta 1: ¿Existe un FORK o PATCH que arregle el bug SWA + checkpoint de Gemma 4?

Buscá MUY a fondo (no me digas "no encontré" sin haber buscado en):
- Pull Requests ABIERTOS (no solo mergeados) en ggml-org/llama.cpp que
  mencionen: "gemma 4 SWA", "ISWA checkpoint", "memory_seq_rm gemma",
  "illegal memory access SWA", "n_swa gemma4", "head_dim mismatched".
  Lista CADA PR con: número, autor, fecha, estado, link.
- Branches experimentales/draft de @ngxson (autor del soporte Gemma 4) o
  @ggerganov en sus forks personales.
- Forks activos: pocketpal-ai, koboldcpp, croco, LostRuins/koboldcpp,
  smallcloudai. Por cada uno: ¿tiene patches específicos sobre el path
  SWA de Gemma 4? Mostrame los archivos `src/llama-memory-recurrent.cpp`,
  `src/llama-kv-cache.cpp`, `src/llama-model.cpp` comparados con upstream.
- PRs cerrados (rejected/superseded) que hayan intentado arreglar el bug
  pero no llegaron a merge. A veces hay un parche válido en código rechazado.

### Pregunta 2: ¿Variables de entorno CUDA u opciones de kernel que evitan el path culpable?

Investigá específicamente para CUDA 12.4 + Ada Lovelace (RTX 4060 Ti):
- `GGML_CUDA_FORCE_CUBLAS`: ¿usar cuBLAS en vez de MMQ evita el crash?
- `GGML_CUDA_FORCE_MMQ`: ¿el path opuesto?
- `GGML_CUDA_PEER_MAX_BATCH_SIZE`: ¿valores específicos cambian el path?
- `CUDA_VISIBLE_DEVICES=0` solo (excluir CPU offload mixto): ¿afecta?
- `CUDA_LAUNCH_BLOCKING=1`: confirmado solo para debug.
- `GGML_CUDA_NO_PINNED`: ¿afecta el seq_rm?
- `GGML_CUDA_ENABLE_UNIFIED_MEMORY`: ¿unified memory cambia el behavior?
- `CUDA_CACHE_DISABLE=1`: ¿desactivar el PTX cache de CUDA hace algo?

Por cada env var: testimonio de usuarios reportando que cambió el behavior
de un crash similar, o NO_FOUND.

### Pregunta 3: ¿Compilar con flags CMake específicos cambia el bug?

Para RTX 4060 Ti (compute 8.9), CUDA 12.4, MSVC:
- `-DGGML_CUDA_FORCE_MMQ=ON` vs `=OFF`: ¿cambia el bug?
- `-DGGML_CUDA_F16=ON`: ¿el modo half-precision atacks evita el path?
- `-DGGML_CUDA_USE_GRAPHS=OFF`: confirmado en #22527 que no fix.
- `-DGGML_CUDA_DMMV_X`, `-DGGML_CUDA_MMV_Y`: parámetros de kernel,
  ¿alguien reportó que valores no-default evitan el crash?
- Compilar con CUDA Toolkit 12.6 o 13.x en vez de 12.4: ¿alguien
  reportó que la versión de CUDA Toolkit afecta este bug?

### Pregunta 4: ¿Workaround a nivel de PATCH MANUAL del código fuente?

Específicamente para los archivos que ejecutan el path culpable:
- `src/llama-memory-recurrent.cpp` — función `llama_memory_seq_rm`:
  ¿es seguro reemplazar la implementación CUDA por el fallback CPU?
- `src/llama-kv-cache.cpp` — KV shifting con SWA: ¿hay forma de
  forzar el reset completo en vez del partial truncation?
- `tools/server/server.cpp` — el slot management: ¿se puede modificar
  para NUNCA llamar a seq_rm parcial (siempre completo o nunca)?
- `ggml/src/ggml-cuda/ggml-cuda.cu:3084` — la función
  `ggml_backend_cuda_synchronize`: ¿existe un PR/patch que la haga
  reentrante o que skip el sync cuando hay flag específico?

Dame el diff exacto (o lo más cercano disponible) de un patch que
funcione, aunque sea hacky.

### Pregunta 5: ¿Wrapper/proxy entre el cliente y llama-server que evite el bug?

Como el bug se dispara cuando llama-server hace `memory_seq_rm`, ¿se puede
poner un proxy HTTP delante de llama-server que:
- Detecte cuando un request va a disparar el seq_rm (en base al estado del
  slot).
- Antes de cada request, fuerce un erase del slot (POST /slots/0?action=erase)
  para que NUNCA haya partial match.
- O reescriba el request para incluir un sentinel token al final que rompa
  el LCP match.

¿Existe algún proxy ya hecho (litellm, ollama-proxy, llama-cpp-python-server,
oai-proxy) que tenga esta capability? ¿O hay que escribirlo desde cero?

### Pregunta 6: ¿El bug se dispara también con Gemma 4 E4B Q4_K_M o solo con E2B?

Si E4B (mismo arquitectura, más params) NO crashea, el modelo más grande
sería opción. Lo importante: ambos usan SWA igual, pero el crash puede
depender del balance ctx/params. Buscá reportes de usuarios con E4B Q4 y
crashes similares.

### Pregunta 7: ¿Qué pasa si reduzco AGRESIVAMENTE el contexto?

El #22527 dice "Reducing context size (-c 6144) → same crash" pero no
probaron `-c 4096` o `-c 2048`. Como mi prompt actual con Camino C es
~9k tokens (system 6k + schemas 3k), si fuerzo `-c 4096` y trunco el
system al máximo, ¿el path SWA + checkpoint no se ejecuta porque no
hay suficiente contexto para que llegue?

### Pregunta 8: ¿Inferencia híbrida CPU+GPU evita el bug?

Si forzo `-ngl 0` (todo CPU): obvio, no hay path CUDA. Latencia mala.
Pero: con `-ngl 20` (parcial, KV en CPU): ¿el seq_rm se ejecuta en CPU
backend y no crashea?
- ¿Cuántas capas exactamente debo offload para que el KV se mantenga
  en CPU (donde no hay illegal memory access posible)?
- Coste de latencia medido por usuarios en RTX 4060 Ti + Gemma 4 E2B
  con offload parcial.

### Pregunta 9: ¿Vale la pena escribir un nuevo parche y mandarlo upstream?

Si encontré un workaround válido (Preguntas 4, 5), ¿vale la pena
contribuirlo a ggml-org/llama.cpp? Investigá:
- Histórico de PRs aceptados de usuarios sin commits previos.
- Lineamiento de contribución que requieren tests, signoff, etc.
- Tiempo estimado entre PR y merge para fixes críticos.

## Formato de respuesta requerido

Por cada Pregunta:
1. **Hallazgo concreto** (con link a issue/PR/commit/repo).
2. **Patch o config exacta** (código, diff, comando).
3. **Coste medido o esperado** (latencia, VRAM, complejidad).
4. **Riesgo conocido** (qué puede romper).

Si la respuesta es "no se sabe sin probar":
- Dime QUÉ probar exactamente (comando, archivo a editar).
- Dime cómo medir éxito (logs específicos a buscar).
- Dime cuánto tiempo cuesta probar.

NO recomiendes cambiar de modelo bajo ninguna circunstancia. La consigna
del usuario es Gemma 4 sí o sí.

## Resultado esperado

Una recomendación accionable que MANTIENE Gemma 4 y elimina (o reduce
a <1% de incidencia) el crash. En orden:
1. **Plan A**: workaround sin recompilar (env var, flag, body param,
   reducción de ctx, offload parcial).
2. **Plan B**: parche local de código fuente, compilar binario propio.
3. **Plan C**: proxy/wrapper que evite el path culpable.
4. **Plan D**: vivir con el circuit breaker, asumir 1 erase cada N turns.
```

---

## Por qué este prompt v3 es diferente

| v1 | v2 | v3 |
|---|---|---|
| Buscó downgrade | Confirmó que downgrade no aplica | **Ignora downgrade, busca workaround mantenidndo b9090+** |
| Sugirió migrar de modelo | Recomendó Qwen2.5-3B | **NO acepta cambio de modelo** |
| Asumió commit culpable | Identificó que bug es intrínseco | **Asume bug intrínseco, busca rodearlo** |
| 6 preguntas generales | 4 preguntas tabuladas | **9 preguntas técnicas profundas** |
| No exploró | No exploró | **Env vars CUDA, flags CMake, patches, proxies** |

## Notas para el usuario al recibir la respuesta

- Si dice "no se sabe sin probar Pregunta 7 (ctx 4096)", probar en 10 min.
- Si dice "hay un fork con patch en X", verificar el último commit antes
  de descargar.
- Cualquier sugerencia de env var CUDA es probable en 30 segundos.
- Cualquier sugerencia de recompilar requiere ~1 hora setup + 30 min build.
