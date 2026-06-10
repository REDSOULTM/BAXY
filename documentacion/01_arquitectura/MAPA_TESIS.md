# Baxy — Mapa de arquitectura (para la documentación de la tesis)

Documento autocontenido y limpio: capas, flujo de un turno e invariantes.
Pensado para copiarse al capítulo de arquitectura. Las cifras y referencias
están verificadas contra el código (2026-06-10).

Baxy es un **asistente de voz local para Windows** sobre el modelo Gemma 4 E2B
fine-tuneado. Todo corre en la máquina del usuario (sin nube): STT (Parakeet),
LLM (llama.cpp), TTS (Piper), y un router de tools propio. ~85k LOC de Python.

---

## 1. Las cinco capas

```
┌──────────────────────────────────────────────────────────────────────┐
│ SUPERFICIES DE ENTRADA                                                 │
│   • voz:  micrófono → wake-word → STT                                  │
│   • texto: UI de escritorio (pywebview) · CLI · servidor HTTP (FastAPI)│
└───────────────────────────┬──────────────────────────────────────────┘
                            │  comando (texto)
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│ HOT-PATH DEL TURNO   (agent_core/agent.py :: run_content)              │
│                                                                        │
│   ROUTER ──► LLM (Gemma 4) ──► DISPATCH de tools ──► VERIFY ──► REPLY  │
│   (qué        (decide qué      (ejecuta cada        (confirma   (texto │
│    tools       hacer)           tool con timeout     por estado  + voz)│
│    ofrecer)                     y try/except)        del SO)            │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐
│ PERSISTENCIA │  │ DIAGNÓSTICOS     │  │ DAEMONS / LIFECYCLE │
│ estado,      │  │ tracing,         │  │ llama-server,       │
│ sesiones,    │  │ telemetría,      │  │ watchers, boot,     │
│ memoria,     │  │ detección de     │  │ EventBus            │
│ experiencia  │  │ loops            │  │ (sin huérfanos)     │
└──────────────┘  └──────────────────┘  └────────────────────┘
```

**Por qué estas capas.** El principio rector es que **el hot-path del turno nunca
debe caerse**: cada cruce a un recurso externo (modelo, disco, proceso) está
contenido con timeout, try/except o recovery. Las capas de soporte (persistencia,
diagnósticos, daemons) cuelgan del hot-path pero un fallo en ellas no tumba el
turno. La auditoría confirmó este patrón: **los bugs reales vivieron en los bordes
(recovery, teardown, daemons), nunca en el camino feliz del dispatch.**

---

## 2. El router (la decisión central, sin hardcodes)

El router NO usa listas de keywords por idioma (sería frágil y monolingüe). Decide
qué tools ofrecerle al LLM combinando varias capas, todas multilingües:

```
comando ──► [encoder multilingüe MiniLM, fine-tuneado]
                 │
                 ├─ similitud semántica contra la descripción de cada tool
                 ├─ per-tool head (clasificador entrenado)
                 ├─ Tool2Vec (centroides por tool desde ejemplos)
                 └─ abstain head (¿es charla y no necesita ninguna tool?)
                 │
                 ▼
           subset de tools ofrecido al LLM  (el LLM elige, no el router)
```

Esto cumple un principio del producto: **el LLM responde, el router solo acota
las opciones.** Lo único determinista permitido son (a) clasificación por
embeddings con fallback seguro, (b) guardas estructurales que miden la FORMA del
reply (no el contenido) para honestidad y anti-loop, (c) resolución por estado del
SO (registro, UIA, procesos), nunca por listas hardcodeadas.

---

## 3. Flujo de un turno (paso a paso)

```
usuario  →  run_content(texto)
   │
   ├─ 1. modo del turno        (fast_action … research; ajusta timeout y presupuesto)
   ├─ 2. ROUTER                 → subset de tools (embeddings, cacheados)
   ├─ 3. system prompt slim     (solo las tools del subset; microagentes cacheados)
   │
   ├─ 4. LLAMADA AL LLM         (timeout por modo) ──► llama-server
   │        └─ recovery: health-poll + 1 retry si el server se reinició
   │
   ├─ 5. ¿pidió tools?  ──► DISPATCH, por cada tool:
   │        ├─ validar args contra el schema
   │        ├─ clasificar riesgo → ¿pedir confirmación? (política configurable)
   │        ├─ ejecutar  [envuelto en timeout + try/except]
   │        └─ VERIFICAR por estado del SO (¿de verdad pasó?) → confirmado / no / no-medible
   │        (loop hasta N turnos, con detección de loops)
   │
   ├─ 6. pase de resumen        (el LLM redacta la respuesta con la evidencia)
   ├─ 7. guardas de honestidad  (no afirmar lo no verificado; idioma del usuario)
   └─ 8. REPLY                  → texto en pantalla  +  voz (Piper TTS)
```

Cada flecha que cruza a un proceso/disco/modelo tiene su contención. Eso es lo que
mantiene el turno vivo siempre.

---

## 4. Invariantes (qué la arquitectura GARANTIZA)

Estos están verificados por tests-guardrail (`test_architectural_invariants`,
`test_god_object_size_ceiling`, `test_router_coverage_invariant`, …):

| invariante | garantía |
|---|---|
| **Blast-radius contenido** | una tool que crashea o cuelga se vuelve `{ok:False}` + timeout — nunca aborta el turno |
| **Verifier no tumba el turno** | un verificador que crashea da `confirmado=False`, no propaga la excepción |
| **Reply nunca destruido** | la decoración cosmética post-LLM va en try/except — un bug tardío no borra una respuesta ya generada |
| **Honestidad estructural** | no se afirma una acción sin evidencia de que ocurrió (medido por la FORMA del reply, multilingüe) |
| **Sin huérfanos** | el llama-server gestionado se cierra en `atexit` (no retiene 6 GB de VRAM); nunca mata uno externo del usuario |
| **Persistencia atómica** | estado y sesiones se escriben con `os.replace` — nunca un JSON truncado; una DB corrupta se pone en cuarentena y se recrea |
| **Sin ciclos de import** | 0 ciclos top-level (verificado); el acoplamiento del núcleo se difiere con imports lazy |
| **El LLM responde** | sin tablas de respuestas enlatadas; lo determinista es solo embeddings + guardas de forma + estado del SO |

---

## 5. Restricciones de diseño (el "por qué" de muchas decisiones)

- **Todo local y OSS**: sin APIs de nube de pago. El STT corre en CPU+int8 porque
  la GPU (6 GB) la consume el LLM.
- **Latencia tier-Alexa**: presupuesto de 4-5 s por turno de voz. Lo costoso va
  off-path, cacheado o decimado; la I/O crítica lleva timeout.
- **Universalidad**: multi-usuario, multi-idioma, multi-acento. Nada se optimiza
  sobre una sola voz; se evalúa contra un held-out diverso.
- **Hardware modesto**: se asume una laptop típica (GPU de 6 GB o sin GPU dedicada).
