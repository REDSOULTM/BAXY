# Investigación necesaria — CUDA illegal memory access en Gemma 4 + llama-server b9090 con flash-attn + swa-full

Este es un prompt para mandar a Claude.ai (con web search y acceso a GitHub),
buscando una solución que NO sacrifique latencia ni calidad. El objetivo no
es resolver el bug en el binario de llama.cpp (no podemos), sino encontrar
**una combinación de flags / configuración / build alternativo / fork** que
nos permita mantener todas estas propiedades simultáneamente:

1. **Estabilidad**: 100+ turns sin crash del child del server.
2. **Latencia per-turn p50 ≤ 500 ms** (prefill + first token).
3. **Cache hit ratio ≥ 80%** turno-a-turno con prompts diversos del usuario.
4. **Modelo Gemma 4 E2B-it Q4_K_M** (no podemos cambiar de modelo).
5. **6 GB efectivos de VRAM** (target es vram4, hardware 16 GB pero conservador).
6. **Visión (mmproj) cargable on-demand** sin perder #1-#5 al cargar.

---

## Prompt para Claude.ai

```
Necesito tu ayuda investigando una solución técnica precisa. NO me ofrezcas
soluciones genéricas; investigá fuentes oficiales (issues de GitHub de
ggml-org/llama.cpp, PRs mergeados, releases, discussions), measure twice
cut once.

## Contexto medido (no asumido)

Tengo un asistente de voz local Windows usando llama.cpp como backend. El
modelo es Gemma 4 E2B-it Q4_K_M (GGUF, ~1.8 GB) en una RTX 4060 Ti 16 GB.
Build: b9090-5757c4dcb (recent stable).

**Flags actuales (router-mode con presets text/vision):**
- --models-preset <file.ini> --models-max 1 --parallel 1 --jinja
- --swa-full --flash-attn on --ctx-size 16384 --ngl 99
- --keep -1 --no-mmap (vision preset adds --mmproj --no-mmproj-offload)
- --ctx-checkpoints 0 (added to prevent earlier crash)
- --cache-ram 2048 --no-cache-idle-slots (added to prevent KV bloat)
- --cache-reuse REMOVED (caused MUL_MAT crash via memory_seq_rm shifting)

**Bug exacto que estoy hitting (REPRODUCIBLE):**

Después de 2-5 chat completions con prompts donde el user msg cambia pero
el system prompt es idéntico, el server crashea con:

```
ggml_cuda_compute_forward: MUL_MAT failed
CUDA error: an illegal memory access was encountered
current device: 0, in function ggml_backend_cuda_synchronize at
  D:\a\llama.cpp\llama.cpp\ggml\src\ggml-cuda\ggml-cuda.cu:3084
cudaStreamSynchronize(cuda_ctx->stream())
```

El logueo justo antes del crash siempre muestra:

```
slot get_availabl: id 0 | task -1 | selected slot by LCP similarity,
  sim_best = 0.997 (> 0.100 thold), f_keep = 0.985
slot launch_slot_: id 0 | task N | processing task
slot update_slots: id 0 | task N | new prompt, n_ctx_slot = 16384,
  n_keep = -1, task.n_tokens = NNN
slot update_slots: id 0 | task N | n_tokens = MMM, memory_seq_rm [MMM, end)
slot update_slots: id 0 | task N | prompt processing done
CUDA error: an illegal memory access was encountered
```

Es decir: el bug se dispara durante el FORWARD pass después del
`memory_seq_rm` que el slot hace cuando hay LCP partial match con el cache.

**Investigaciones previas que ya hice:**

1. **llama.cpp issue #22527** "Gemma 4 31B: illegal memory access after SWA
   KV cache checkpoint with Flash Attention enabled" — el bug es REGISTRADO
   pero sin fix oficial. Confirma:
   - Disabling Flash Attention → VRAM allocation failures
   - Reducing context sizes → no fix
   - --cache-ram 0 → solo delaya el crash
   - Disabling CUDA Graphs → no fix
   - q8_0 KV cache → OOM

2. **llama.cpp issue #17109** "CUDA error during K-Shift" — el bug se reproduce
   con la secuencia llama_memory_seq_rm → seq_add → seq_cp → decode. Sin
   fix oficial.

3. **llama.cpp issue #21383** "Qwen3.5 CUDA illegal memory access regression
   in prompt cache (agentic tool-call pattern)" — bug muy similar en Qwen,
   también con tool-calling y prompt cache. Sin fix oficial.

4. **llama.cpp PR #22288** ya está mergeado en b9090 y supuestamente arregla
   el SWA con swa-full para Gemma 4. Pero el crash persiste, lo que indica
   que NO arregla el caso flash-attn + swa-full + LCP partial match.

5. **Informe de research interno (prefill_latency_llama_server_gemma4.md)**
   menciona que ggerganov describe --cache-reuse como "misleadingly named
   processing trick to keep tail end after deleting earlier parts". Lo
   quitamos y el crash persiste igual, lo que indica que el problema NO es
   solo cache-reuse sino el slot management con LCP partial match.

## Lo que necesito que investigues

Por favor buscá EXHAUSTIVAMENTE y devuélveme respuestas concretas para:

### Pregunta 1: ¿Existe un build de llama-server que NO tenga este bug?

- ¿Qué build/commit hash es el "último estable" para Gemma 4 + flash-attn
  + swa-full antes de la regresión documentada en marzo-abril 2026?
- El issue dice "rollback a commit 149b2493c resuelve". ¿Qué versión de
  release es ese commit (b8XXX)? ¿Hay binarios pre-built de Windows CUDA
  para ese build?
- ¿Hay forks (ik_llama.cpp, etc) que tengan parches para este bug en
  particular?
- ¿Hay un build/branch experimental de ggml-org/llama.cpp donde el fix
  esté en review?

### Pregunta 2: ¿Hay una combinación de flags que sí funcione SIN sacrificar latencia?

Lo que NO sirve (medido o documentado en issue #22527):
- --no-flash-attn (causa OOM)
- --no-swa-full (pierde 80% cache hit, +1.5-2s prefill)
- --cache-ram 0 (delaya pero no fix)
- --no-cuda-graphs (no fix)
- ctx-size pequeño (no fix)

¿Hay algún flag MENOS común que ataque el slot management LCP partial match?
Investigá:
- --slot-prompt-similarity 0.0 (default 0.10): ¿forza nuevo slot siempre? ¿Sirve?
- --no-context-shift: ¿interactúa con el seq_rm?
- --no-prompt-cache vs --cache-prompt false: ¿qué hace exactamente cada uno?
- --kv-unified / --no-kv-unified: ¿afecta el seq_rm path?
- Variables de entorno LLAMA_ARG_* relacionadas con cache.
- Flags de CUDA específicos: GGML_CUDA_NO_PINNED, GGML_CUDA_FORCE_MMQ,
  CUDA_LAUNCH_BLOCKING=1, etc.

### Pregunta 3: ¿Existe una API path en llama-server que EVITE el LCP partial match?

- ¿El endpoint `/v1/chat/completions` se puede configurar para NUNCA hacer
  seq_rm parcial (siempre full reprocess o siempre prefix-only)?
- ¿Hay un endpoint que use prompt-token IDs en vez de chat messages, donde
  el cliente controle el match exactamente?
- ¿`prompt_cache: false` en el request body funciona como override por
  request?
- ¿Hay un parámetro `cache_prompt: false` por request?

### Pregunta 4: ¿Vale la pena migrar a otro runtime?

Para Gemma 4 + Q4_K_M + 16 GB VRAM + tool calling + visión + Spanish:
- **vLLM 0.7+** con GGUF support: estado real (no marketing) en 2026-05.
  ¿Es viable o el GGUF está "experimental and under-optimized"?
- **llamafile**: ¿está al día con Gemma 4?
- **mlx (Apple Silicon)**: descartado (Windows host).
- **TabbyAPI/ExLlamaV2**: requiere convertir a EXL2, ¿hay quants Gemma 4
  estables y mantienen quality?
- **TensorRT-LLM**: ¿soporta Gemma 4 en 2026-05?
- **Ollama**: usa llama.cpp internamente, mismo bug presumiblemente.

Si alguno NO tiene este bug, dame: comando de instalación Windows, comando
de arranque equivalente a nuestro setup llama-server, y medición conocida
de latencia per-turn comparable.

### Pregunta 5: ¿Estrategia de mitigación en el cliente para evitar disparar el bug?

Si el bug es por LCP partial match → seq_rm, entonces si el CLIENTE evita
mandar prompts que provoquen ese patrón, el bug no se dispara. Investigá:
- ¿Existe el patrón "tokens canónicos al final del prompt" (sentinel tokens)
  para que el LCP siempre sea 100% o 0%?
- ¿Si el cliente cachea su propio prompt_tokens y reenvía con prefix
  exact-match cada vez, llama-server hace seq_rm igual o lo evita?
- ¿Hay un slot.tokens reset que el cliente puede triggerear (vía /slots
  endpoint) entre turnos para forzar slot vacío?
- ¿`POST /slots/0?action=erase` existe y rompe el cache pero evita el bug?

### Pregunta 6: ¿El bug es model-specific? ¿Qué modelos NO lo tienen?

- ¿Llama 3.1 8B con mismo setup (flash-attn + swa-full + Q4) tiene el bug?
- ¿Qwen2.5 7B?
- ¿Phi 4?
- ¿Mistral Small?
Si hay un modelo de tamaño similar a Gemma 4 E2B (~2-3B params) que NO
tenga el bug Y soporte tool-calling decente, sería una alternativa real.

## Formato de respuesta que necesito

Por cada pregunta, dame:
1. **Respuesta corta** (1-2 líneas): SÍ/NO/condicional.
2. **Evidencia** (links a issues, PRs, releases, commits específicos).
3. **Acción concreta** (comando exacto, flag exacto, archivo a descargar).
4. **Costo medido o estimado** (latencia, VRAM, calidad).
5. **Caveats** (qué puede salir mal, qué necesitas verificar antes).

Si no encontrás solución para alguna pregunta, decímelo explícito (NO
inventes una solución plausible). Mejor "no hay fix conocido" que "probá
estas 5 flags por las dudas".

NO dame paths genéricos ("revisá si tu CUDA driver está actualizado",
"probá con menos GPU layers"). Necesito respuestas específicas para
Gemma 4 + b9090 + flash-attn + swa-full + LCP partial match path.

## Resultado esperado

Al final del análisis, debería poder elegir UNA de estas vías con datos:
- (A) Cambiar a build/binario X y sigo con todos los flags.
- (B) Agregar/quitar flag Y y el bug desaparece.
- (C) Cambiar el cliente para usar endpoint/flag Z del request.
- (D) Migrar a runtime W con costo medido de migración.
- (E) Convivir con el bug y reiniciar el server cada N turns (vía
      circuit breaker en el cliente).

Para cada opción quiero el trade-off cuantificado.
```

---

## Notas para el usuario al recibir la respuesta de Claude.ai

1. **NO aplicar ciegamente** lo que diga. Verificá cada link a un issue
   real (puede inventar URLs).
2. **NO aceptar "probá con --flag-X"** sin que muestre evidencia (un
   issue/PR/discussion) de que ese flag específicamente arregla este
   bug.
3. **Si propone downgrade de build**: pedir el SHA-256 del binario que
   estamos descargando y verificarlo contra el release oficial.
4. **Si propone migrar runtime**: pedir benchmark de latencia comparable
   con números medidos por terceros (no marketing del proyecto).
5. **Cualquier cambio de flag**: probar primero el stress test de 30
   prompts diversos antes de declarar éxito.

## Test de validación post-fix

```python
# stress_test_cuda_crash.py — corré esto antes/después de cualquier fix.
# Si el server sobrevive 30 prompts diversos con thinking, el fix funciona.
import json, urllib.request, time
prompts = [
    'Abre steam', 'Pone musica', 'Cierra ventana', 'Sube volumen', 'Abre chrome',
    'Manda whatsapp a juan', 'Que ves en pantalla', 'Conecta wifi', 'Busca tutoriales',
    'Hace screenshot', 'Hora actual', 'Que hace este programa', 'Cierra steam',
    'Baja volumen', 'Abre notepad', 'Toma nota: comprar pan', 'Que tengo abierto',
    'Mute', 'Abre opera', 'Pausa musica', 'Reanuda musica', 'Siguiente cancion',
    'Apaga pantalla', 'Bloquea pc', 'Que pelicula vimos', 'Cierra chrome',
    'Cambia a vram4', 'Activa modo cine', 'Sube brillo', 'Pone alarma 8am',
]
big_sys = 'You are a helpful local agent. Be concise.\n' * 200
failures = 0
for i, prompt in enumerate(prompts):
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
    except Exception as e:
        failures += 1
        print(f'{i:2d} {prompt[:30]:<32} FAIL')
print(f'Result: {30-failures}/30 OK')
```
