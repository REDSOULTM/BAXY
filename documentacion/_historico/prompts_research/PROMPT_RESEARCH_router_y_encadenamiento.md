# Prompt de investigación — Encadenamiento multi-paso + foco/maximize + latencia (Carter Agent)

Copiá esto a claude.ai (con research/web). Contiene la arquitectura REAL del
sistema (extraída del código, con rutas y snippets) para que investigues sobre
nuestra arquitectura concreta, no sobre supuestos. Devolveme un informe técnico
ACCIONABLE con código/pseudocódigo listo para implementar. Prioridad: A y B son
el cuello de botella de UX; C y D son secundarios pero deseados.

---

## 0. Stack exacto (verificado en código, 2026-05-23)

- **Modelo**: Gemma 4 **E4B-it**, cuantización **Q4_K_M** (~4.6 GB), GGUF.
  `models/E4B/gemma-4-E4B-it-Q4_K_M.gguf` + `mmproj-F16.gguf` (visión).
  Es la familia Gemma 4 (recién salida). Perfiles por VRAM (vram3..vram16):
  los chicos = E2B/E4B-Q4, los grandes = E4B-Q6 / 26B-A4B MoE Q2_K_XL. Target
  runtime: laptop, GPU 6 GB o sin GPU dedicada.
- **Runtime**: **llama.cpp `llama-server`** (build b9090+), un solo slot.
  Flags reales (gemma4_agent/llama_server.py:324):
  `--jinja --ctx-checkpoints 1 --flash-attn on --keep -1 --cache-reuse 256
   --swa-full -ngl 99 -c <ctx> --parallel 1`.
  `--swa-full` es CRÍTICO: Gemma usa Sliding Window Attention (n_swa=512); sin
  él el KV cache evicta el prefijo del system prompt y CADA turno reprocesa
  ~6K tokens (~6s prefill). Con swa-full + cache-reuse el prefix se reutiliza.
- **¿Abierto a otro runtime?** Preferimos quedarnos en llama.cpp (es lo que
  cumple "100% local, OSS, GGUF, 6GB"). vLLM/TGI solo si el ROI de latencia es
  enorme Y corre en 6GB sin romper el resto. Asumí llama.cpp salvo que la
  evidencia diga lo contrario.
- **Restricciones duras**: 100% local, OSS, gratis; latencia tier-Alexa (4-5s
  tope por turno de voz, 8s = catastrófico); multi-usuario/multi-idioma; CPU
  para STT (GPU es del LLM). STT ya migrado a Parakeet-TDT-v3 (no es el tema acá).

## 1. Arquitectura del ROUTER (clave para A y B)

El sistema NO le pasa los 65 tools al LLM en cada turno (inflaría el contexto y
la latencia). Un pipeline de routing elige un SUBCONJUNTO por turno:

1. **`semantic_router.py`** — `suggest_tools_scored(query, k)`:
   embeddings con `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers)
   + **Tool2Vec** + fusión **RRF** (Reciprocal Rank Fusion) sobre descripciones
   de tools. Encoder fine-tuneado en `data/router_encoder_ft`. Devuelve
   [(tool, score)]. (router rebuild 2026-05-21: holdout recall 0.835→0.881.)
2. **`intent_router.py`** — `classify_intent(text) -> IntentScores(info, action,
   margin)` y `wants_knowledge(text)`: clasificador semántico 2-clases por
   ANCLAS multilingües ("¿es pregunta de conocimiento?" vs "¿es acción en la
   compu?"). Centroides = media de embeddings de frases-ancla en varios idiomas.
   Margen vs acción configurable (GEMMA4_INTENT_VS_ACTION=0.05).
3. **`abstain_head.py`** — gate "no-tool" (probabilidad de que sea charla, no
   comando), con features de intent + scored + keyword.
4. **`planner.py`** — orquesta: combina wants_knowledge + scored + abstain para
   decidir el subset final de tools y si encadenar pasos.

**HALLAZGO CRÍTICO de esta sesión** (ya arreglado, pero ilustra la fragilidad):
instalar `torchcodec` rompió `sentence-transformers` → el router devolvía
classify_intent=None y suggest_tools=[] SILENCIOSAMENTE → todo se mis-ruteaba
("¿qué es Mortal Kombat?" creó un documento porque el fallback solo ofrecía
`office`). Tras `pip uninstall torchcodec`: classify_intent info=0.48>action=0.30,
top tool=`web`. Lección: **el router degrada en silencio y arrastra todo**.

## 2. Los problemas a resolver (evidencia de logs reales, sesión #847)

### Problema A — Router/clasificador de intención robusto y AUTO-DIAGNOSTICABLE
Aun con el modelo cargado, "¿Qué es X?" con nombres propios (juegos/pelis/apps)
acerca el embedding a tools de creación/office y compite con la rama info.
Buscamos: (a) hacer el clasificador info-vs-acción MÁS robusto a nombres propios
sesgantes; (b) que el router DETECTE cuando su propio modelo no cargó y degrade
de forma segura/visible (no a un subset arbitrario). ¿Reglas sintácticas como
respaldo (¿qué/quién/por qué + "?")? ¿Un gate de intención ANTES del retrieval?
¿Cómo combinarlo con el RRF existente sin romper holdout recall 0.881?

### Problema B — El LLM no ENCADENA pasos multi-tool
"Abre el primer Word que encuentres en mi carpeta de descargas" → el LLM llamó
`filesystem(action=search, pattern=*.docx)` (encontró archivos) pero NO encadenó
`office(action=open, path=<el encontrado>)`. Antes incluso llamó `office(open)`
SIN path → falló y respondió "no me diste ruta" aunque la tenía del search.
El router AHORA ofrece [filesystem, app, local_search] para esa query (bien),
pero el LLM (E4B-Q4, modelo chico) no usa el resultado de tool_A como input de
tool_B. Buscamos: patrones FIABLES de encadenamiento en LLMs pequeños locales
(ReAct, planner explícito multi-step, reflexión sobre tool_result, forzar
re-evaluación tras cada tool, "scratchpad"). Qué funciona <10B con tool-calling
vía --jinja en llama.cpp. ¿Conviene un planner determinista para patrones
conocidos (search→open, search→play) en vez de depender del LLM?

### Problema C — Garantía DETERMINISTA de foco+maximize antes de input GUI
Al teclear/clickear en apps (WhatsApp, Spotify) por GUI, a veces la ventana está
minimizada/sin foco y la acción falla o va a la ventana equivocada. Hoy hay
`window(action=focus)` que hace restore+maximize, y los flujos GUI verifican el
título de la ventana activa antes de teclear (ej. _whatsapp_send_via_gui_search
en domain_tools.py hace focus→sleep→verify "whatsapp" in active_title, y aborta
si no). Pero NO es 100% fiable. Buscamos: mejores prácticas Windows para
asegurar foreground+maximize ANTES de enviar teclas, en CÓDIGO (no dependiendo
del LLM): SetForegroundWindow + ShowWindow(SW_RESTORE/SW_MAXIMIZE) +
AttachThreadInput (para el lock de foreground de Windows), UIA SetFocus, cómo
verificar de forma confiable y cuántos reintentos. Tipeo ya es robusto a Unicode
(clipboard-paste).

### Problema D — Latencia del primer tool-call
YOU→TOOL es 4-5s consistente (TTFT + decode del tool-call); algunas respuestas
finales suman hasta 10s. Ya se bajó de 16-22s→3-7s (Q4_K_M + --swa-full +
--cache-reuse + system prompt LEAN ~920 tok para vram3-8). Buscamos más ROI SIN
cambiar de modelo ni degradar tool-calling: prefix-cache reuse entre turnos
(¿estamos exprimiéndolo?), speculative decoding en llama.cpp (draft model),
grammar/GBNF-constrained decoding para tool-calls (¿acelera el primer token y
mejora fiabilidad?), warm KV, tamaño de subset de tools vs latencia. Qué da el
mayor ROI en E4B-Q4 / 6GB.

## 3. Qué necesito en el informe

Para CADA problema (A–D): diagnóstico, opciones con tabla comparativa (criterios
medibles), fuentes oficiales/papers/benchmarks RECIENTES, y veredicto de qué es
viable en ESTE stack (Gemma 4 E4B-Q4, llama.cpp b9090+, 6GB, tier-Alexa,
multilingüe). Snippets de código/pseudocódigo listos para implementar (Python +
flags de llama-server donde aplique). Distinguí lo confirmado de lo hipotético.
Prioridad alta: A (router robusto/auto-diagnóstico) y B (encadenamiento).
