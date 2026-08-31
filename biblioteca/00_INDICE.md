# La biblioteca — todo lo que ya se investigó

**1.350 documentos** de las cuatro escrituras anteriores de este proyecto, desde el
primer Carter hasta hoy. Estudios, auditorías, investigaciones encargadas,
benchmarks, planes de arquitectura y —lo más valioso— **rechazos con el mecanismo
entendido**.

Existe por una razón: **que nadie vuelva a investigar lo que ya está investigado.**
Antes de abrir una línea de trabajo, busca aquí. La ley 1 de los goals empieza
precisamente por esto.

- **¿No sabes qué leer?** Sigue leyendo: abajo está lo que responde cada área.
- **¿Buscas algo concreto?** [`01_INVENTARIO.md`](01_INVENTARIO.md) lista los 1.350
  con su título, para buscar por palabra.
- **Lo que midió el BAXY actual no está aquí**, está en
  [`../documentacion/`](../documentacion/) y sobre todo en el registro de
  mantenibilidad. Esta biblioteca es lo *anterior* a este repositorio.

## La genealogía, para saber qué estás leyendo

El README de `Probando Gemma 4` lo dice literal: *«el proyecto se renombró a Baxy
(antes Gemma 4 Agent, brevemente Carter)»*. **No son proyectos distintos: es el
mismo, escrito cuatro veces.** Por eso lo que falló ahí falló aquí.

| Carpeta | Qué generación es | Documentos |
|---|---|---:|
| [`carter/`](carter/) | Carter, de v1 a v5. La identidad escrita más clara y el autodiagnóstico de por qué fracasó | 672 |
| [`gemma4-agent/`](gemma4-agent/) | Gemma 4 Agent → Baxy. La investigación más profunda: voz, router, visión, latencia | 636 |
| [`functiongemma/`](functiongemma/) | El experimento de fine-tuning y modelo de habla | 28 |
| [`referencias-externas/`](referencias-externas/) | Proyectos de terceros que se estudiaron | 14 |

`JRVS` no está: es otro producto —operaciones self-hosted para equipos en
industrias reguladas— y no comparte linaje.

---

## Lo primero que hay que leer, si sólo vas a leer cinco cosas

**1. [`carter/la-razon-de-carter/11_lecciones_v1_a_v4.md`](carter/la-razon-de-carter/11_lecciones_v1_a_v4.md)**
Por qué el proyecto fracasó cuatro veces, escrito por él mismo tras 345 commits.
De aquí sale la ley 2 de los goals: *«el proyecto crece por acumulación, no por
reemplazo»*, tres routers en serie, ocho capas de reescritura, `agent.py` a 1.397
líneas contra su propio objetivo de 400.

**2. [`carter/la-razon-de-carter/09_progresion_iteraciones.md`](carter/la-razon-de-carter/09_progresion_iteraciones.md)**
La progresión honesta de las iteraciones. Corto y desagradable de leer, que es
justo lo que lo hace útil.

**3. [`carter/la-razon-de-carter/01_auditoria_arquitectura.md`](carter/la-razon-de-carter/01_auditoria_arquitectura.md)
y [`02_auditoria_implementacion.md`](carter/la-razon-de-carter/02_auditoria_implementacion.md)**
Las dos auditorías que separaron lo que la arquitectura prometía de lo que la
implementación hacía.

**4. [`carter/la-razon-de-carter/14_auditoria_competidores.md`](carter/la-razon-de-carter/14_auditoria_competidores.md)**
Diez competidores auditados uno por uno. Antes de mirar el mercado otra vez, mira
esto y actualiza sólo lo que cambió.

**5. [`gemma4-agent/documentacion/README.md`](gemma4-agent/documentacion/README.md)**
La puerta a la documentación por temas del Baxy anterior, que es donde está la
investigación técnica más profunda de todo el linaje.

---

## Qué pregunta responde cada área

### Voz, wake word y transcripción — 25 documentos

[`gemma4-agent/documentacion/03_voz_stt/`](gemma4-agent/documentacion/03_voz_stt/)

**Es el área con más investigación de todo el proyecto.** Si vas a tocar el goal
09, esto te ahorra semanas. Dentro de `research/`:

- **STT en español con code-switching:** `asr_local_codeswitching_hardware.md`,
  `stt_biasing_contextual_spanglish_cpu.md`,
  `whisper_small_cpu_spanglish_accuracy.md`.
- **Parakeet, medido y afinado:** `REPORTE_NOCHE_STT_PARAKEET_2026_05_23.md`,
  `parakeet_v3_uso_correcto_2026-06-10.md`, `spike_sherpa_parakeet.md`,
  `plan_sherpa_parakeet_cpu_optimizacion.md`,
  `parakeet_beam_nombres_propios_decoding.md`,
  `sherpa_parakeet_hotwords_nombres_propios.md`.
- **Nombres propios y sesgo contextual:** `biasing_options.md` — el problema de que
  reconozca «BAXY» y no «vas y».
- **Wake word:** `wake_v5_diseno_entrenamiento_2026-06-11.md`,
  `wake_ruido_fondo_2026-06-11.md`, `PLAN_MAESTRO_wake_carter.md`,
  `HISTORIAL_nombres_wake_word.md`.
- **Optimización en CPU:** `faster_whisper_int8_cpu_optimizacion.md`.
- **Latencia medida:** `latency_ab_measurements_2026_05_23.md`.

### Router y comprensión — 14 documentos

[`gemma4-agent/documentacion/02_router/`](gemma4-agent/documentacion/02_router/)

El goal 03 arranca aquí, no de cero. Hay un router **entrenado** y su historial de
sprints. En `research/`: `1_toolcalling.md`, `7_nlu.md`,
`07_SKILL_RETRIEVAL_research.md`, `08_MICROAGENT_RETRIEVAL_research.md`.

Y en Carter: [`carter/la-razon-de-carter/15_skills_para_bench_540.md`](carter/la-razon-de-carter/15_skills_para_bench_540.md)
y [`06_benchmark_540.md`](carter/la-razon-de-carter/06_benchmark_540.md) — la
medición pre/post refactor donde salió el **−68 % de tokens al consolidar a 16
herramientas**.

### Operar aplicaciones (computer use) — 13 documentos

[`gemma4-agent/documentacion/04_computer_use/`](gemma4-agent/documentacion/04_computer_use/)

El núcleo del goal 07. `research/` trae investigación propia y externa:
`computer_use_investigacion_propia_2026_05_24.md`,
`computer_use_sintesis_decisional_2026_05_24.md`,
`11_plan_computer_use_windows_4b.md`, `gui_eval_informe_por_tier_2026_05_24.md`,
`8_gui.md`, `3_verificacion.md`.

Y el caso concreto que cierra el círculo:
[`carter/la-razon-de-carter/18_steam_tool_solucion.md`](carter/la-razon-de-carter/18_steam_tool_solucion.md)
— «instala doom eternal», que es literalmente el ejemplo de misión compuesta.

### Visión y cámara — 8 documentos

[`gemma4-agent/documentacion/05_vision_camara/`](gemma4-agent/documentacion/05_vision_camara/)

Incluye `INVESTIGACION_eye_tracking_webcam_comercial.md`.

### VRAM y estabilidad — 5 documentos

[`gemma4-agent/documentacion/06_vram_estabilidad/`](gemma4-agent/documentacion/06_vram_estabilidad/)

Y sobre todo [`carter/la-razon-de-carter/13_carter_v5_perfiles_vram.md`](carter/la-razon-de-carter/13_carter_v5_perfiles_vram.md):
perfiles de VRAM detallados. La ley 4 de los goals vive de esto.

### Latencia — 7 documentos

[`gemma4-agent/documentacion/07_latencia/`](gemma4-agent/documentacion/07_latencia/)

El goal 08 empieza aquí: `prefill_latency_llama_server_gemma4.md`,
`reducir_latencia_thinking_gemma4.md`, `4_contexto.md`.

### Memoria y comportamiento proactivo — 5 documentos

[`gemma4-agent/documentacion/08_memoria_jarvis/`](gemma4-agent/documentacion/08_memoria_jarvis/)

`research/2_memoria.md` y `5_jarvis.md`, más
`DISENO_jarvis_proactivo_2026-06-07.md` y `_JARVIS_auditoria_2026-06-07.md`.

### Fine-tuning y cuantización — 9 + 28 documentos

[`gemma4-agent/documentacion/09_finetune/`](gemma4-agent/documentacion/09_finetune/)
y [`functiongemma/`](functiongemma/)

Aquí está el diagnóstico que el goal 06 necesita: **la cuantización Q2 producía
palabras inventadas** («fysico», «lumínar») y rompía la persona; Q4_K_XL QAT lo
arregló en ~1,5 GB, y el modelo decía «Soy Baxy» **sólo con el system prompt, sin
fine-tuning**. Mira `functiongemma/raiz/README_FINETUNE.md`,
`README_SPEECH_MODEL.md` y `SPEC_SPEECH_PIPELINE.md`.

Y el historial de reentrenamientos que **no** hay que repetir:
`_PLAN_REFINETUNING_2026-06-05.md`, `_REFINETUNING_v1_RESULTADO_2026-06-05.md`,
`_ROUTER_RETRAIN_REPORT_2026-06-18.md`, `_ROUTER_RETRAIN_V3CORPUS_2026-06-11.md`.

### Auditorías completas — 8 + 9 documentos

[`gemma4-agent/documentacion/10_auditorias/`](gemma4-agent/documentacion/10_auditorias/)
y [`11_research_recibido/investigaciones_recibidas/`](gemma4-agent/documentacion/11_research_recibido/investigaciones_recibidas/)

La «auditoría 360» en tres informes, más `0_arquitectura_general.md` y
`9_computer_use_gui.md`. Y en la raíz, `OVERNIGHT_AUDIT_REPORT.md`.

### Arquitectura de Carter v5 — el diseño más elaborado

[`carter/la-razon-de-carter/12_carter_v5_arquitectura.md`](carter/la-razon-de-carter/12_carter_v5_arquitectura.md),
más [`16_openclaw_vs_carter.md`](carter/la-razon-de-carter/16_openclaw_vs_carter.md)
y [`17_openclaw_port_completado.md`](carter/la-razon-de-carter/17_openclaw_port_completado.md)
— análisis profundo de un competidor y la portación que salió de él.

### El histórico crudo — 198 documentos

[`gemma4-agent/documentacion/_historico/`](gemma4-agent/documentacion/_historico/)

Sesiones, handoffs y benchmarks sin curar. No lo leas entero: **búscalo por
palabra** en el inventario cuando persigas algo concreto.

---

## Cómo se usa esto sin perder el día

1. **Busca antes de investigar.** Palabra clave en
   [`01_INVENTARIO.md`](01_INVENTARIO.md), o `grep` sobre `biblioteca/`.
2. **Mira la fecha.** El inventario la trae en cada fila. Una comparativa de
   modelos de hace ocho meses eligió entre candidatos que hoy ya no existen: **la
   conclusión caduca, el método y el mecanismo no.**
3. **Un rechazo vale tanto como un hallazgo.** Si algo se midió y murió, no lo
   repitas — a menos que haya cambiado el supuesto que lo mató, y entonces dilo.
4. **Esto es evidencia, no instrucción.** Lo que hay que hacer lo dice tu goal;
   qué es BAXY lo dice [`../documentacion/00_IDENTIDAD.md`](../documentacion/00_IDENTIDAD.md).
   Nada de aquí manda sobre ellos: todos estos documentos pertenecen a versiones
   que se reescribieron.

## Qué no está aquí, a propósito

Código, modelos, checkpoints, corpus y binarios. Esto es **documentación e
investigación**. Los repositorios originales siguen en la carpeta `Programacion` y
conservan todo lo demás intacto — el goal 01 es quien decide qué se hereda de ahí.

Tampoco están las copias de proyectos de terceros que se clonaron para estudiarlos
(openclaw, goose, AutoGPT, LangGraph, promptfoo, llama.cpp y demás): su
documentación es suya y está en su sitio. Lo que sí está es **el análisis propio**
que salió de estudiarlos.

<!-- goal095-12-generated:begin -->
# Reconciliación 09.5 — linaje publicado

Generado por `scripts/goal095_09512_integrate.py` desde manifiestos y síntesis. Goal 01 cerrado el **2026-08-16**. No copia secretos, binarios ni corpus privados.

## Las cuatro clases

### Herencia previa

Fuentes ya contempladas el 2026-08-16: `Carter OS AI`, `Probando Gemma 4`, `FunctionGemma`, `BAXY`, biblioteca 1.350 documentos, mapa `00_MAPA.md` §1–§10. Schema Agent se audita en el historial Git de `BAXY`, no como carpeta hermana. `JRVS` y `Probando schemas` siguen fuera.

### Delta nuevo

Manifiesto 09.5.1: 28373 archivos hasheados; cola 19512; duplicados 8348; cobertura previa 513; faltantes 0; solapes 0. Cobertura 100 %.
Llegó material intelectual adicional en los mismos árboles, la etapa Schema Agent dentro de `BAXY`, y la declaración de fuente dispersa (GGUF/datasets/checkpoints de Probando Gemma 4 omitidos a propósito; hashes individuales not invented).

### Piezas trasplantadas

Cero lotes. `pending=0` `claimed=0` `complete=0` `total=0`. Decisión 09.5.9/10: `conservar_actual`. Un trasplante vacío es un hecho medido, no un hueco a rellenar.

09.5.5–09.5.8 no hallaron pieza histórica que gane al vivo en conducta, pruebas, recursos y arquitectura a la vez. Cero reusar_exacto, cero adaptar, cero medir_antes de herencia: unload-on-idle y arranque frío son mediciones de producto del Goal 10.2 sobre el keep-warm/process_lifecycle vigentes, no un vram_manager/Ollama/ui_field que transplantar. Los GGUF/datasets/checkpoints dispersos de Probando Gemma 4 no se nombran para reutilizar (hashes not invented). Cada lote de herencia habría tenido que retirar el mecanismo vivo en el mismo cambio; no hay tal lote. Rechazos protegidos (FunctionGemma en pesos, Qwen-VL R-023, Ollama/servicio Windows, AUTO_APPROVE, soak 24 h como requisito, Gemma-native-audio como oído) no reentran.

### Rechazos

Protegidos (no reentran): `functiongemma-270m-ft`, `qwen-vl`, `ollama-runtime`, `auto_approve`, `soak-24h-as-requirement`, `gemma-native-audio`.

Decisiones 09.5.9 por terminal: {"conservar_actual": 61, "rechazar": 35}.

## Campañas

| Campaña | pending | claimed | complete | total |
|---|---:|---:|---:|---:|
| `docs` | 0 | 0 | 25 | 25 |
| `code_tests` | 0 | 0 | 477 | 477 |
| `evidence_assets` | 0 | 0 | 132 | 132 |
| `transplant` | 0 | 0 | 0 | 0 |

## Hashes de manifiesto 09.5.0 (reproducibles)

- `functiongemma` `ff150df27808ca19c7a80fe40127011ef050be170b83bcd28bacf8d56f619eaa` (match)
- `probando_gemma4` `72f9e5fc6597be5169c99e282d33749d6f7537813fb824809beb85e1b13c7e71` (match)

## Tarjetas 09.5.9 → valor 10/11

| Id | Decisión | valor_10_11 |
|---|---|---|
| `llm_decisor` | `conservar_actual` | 10.0/10.7 comprensión y prosa |
| `cuantizacion` | `conservar_actual` | 10.2 techo VRAM |
| `runtime_inferencia` | `conservar_actual` | 10.0 runtime |
| `encoder_recuperador` | `conservar_actual` | 10.7/03 revalidación shortlist |
| `puerta_abstencion` | `conservar_actual` | 10.7 abstención honesta |
| `catalogo_tipado` | `conservar_actual` | 10.1 corpus / 11 contratos |
| `verificador_identidad` | `conservar_actual` | 10.7 no inventar operaciones |
| `functiongemma-270m-ft` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-e2b-qat` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-e4b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-26b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma4-31b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3.5-4b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3.5-0.8b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3-4b-instruct-2507` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3-8b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen2.5-7b-instruct` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `hermes3-8b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `phi-4-mini` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `lfm2.5-1.2b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `embeddinggemma-300m` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `minilm-l12-tool2vec` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen3-embedding-0.6b` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `bge-m3` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `cross-encoder-reranker` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `ollama-runtime` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `agent-function-schema` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `q2-quant-gemma` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `kva-abstain-head` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen-vl` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `qwen-asr` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `gemma-native-audio` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `wake_word` | `conservar_actual` | 10.11 audio / 10.2 presencia |
| `falsos_disparos` | `conservar_actual` | 10.2 presencia (no retocar 0,5) |
| `ruido` | `conservar_actual` | 10.11 |
| `vad` | `conservar_actual` | 10.11 primera señal oído |
| `stt` | `conservar_actual` | 10.11 |
| `nombres_propios` | `conservar_actual` | 10.11 (aplazado, no bloquea) |
| `bilingue_spanglish` | `conservar_actual` | 10.7 / 10.11 |
| `tts` | `conservar_actual` | 10.11 |
| `primera_senal_oido` | `conservar_actual` | 10.2 / 08 |
| `barge_in` | `conservar_actual` | 10.11 |
| `audio_ducking` | `conservar_actual` | 10.11 |
| `dispositivos_audio` | `conservar_actual` | 10.2 preflight |
| `modelos_assets_voz` | `conservar_actual` | 10.0 / 10.11 |
| `voz_latencia` | `conservar_actual` | 10.2 / 10.11 |
| `voz_recursos` | `conservar_actual` | 10.2 |
| `presencia` | `conservar_actual` | 10.2 presencia diaria |
| `tools` | `conservar_actual` | 10.1 / 10.16 |
| `skills` | `conservar_actual` | 10.16 no es un segundo motor |
| `microagentes` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `uia_ocr_vision` | `conservar_actual` | 10.10 apps/ventanas/visión |
| `adapters_providers` | `conservar_actual` | 10.10 / 10.12 (no hereda allowlist) |
| `planes` | `conservar_actual` | 10.16 misiones |
| `confirmacion` | `conservar_actual` | 10.17 identidad |
| `verificacion` | `conservar_actual` | 10.0 / 11 verificación |
| `steam_media` | `conservar_actual` | 10.12 / 10.16 |
| `archivos` | `conservar_actual` | 10.14 |
| `apps` | `conservar_actual` | 10.10 |
| `navegador` | `conservar_actual` | 10.9 / 10.15 |
| `office` | `conservar_actual` | 10.14 |
| `comunicacion` | `conservar_actual` | 10.15 |
| `sistema` | `conservar_actual` | 10.13 |
| `conectividad` | `conservar_actual` | 10.13 |
| `mision_compuesta` | `conservar_actual` | 10.16 |
| `routers_en_serie` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `listas_hardcodeadas_por_app` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `respuestas_fijas` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `exitos_no_verificados` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `simple-app-open-notepad` | `conservar_actual` | 10.16 C10 |
| `simple-audio-volume` | `conservar_actual` | 10.16 |
| `simple-note-create` | `conservar_actual` | 10.16 / 10.14 |
| `chained-steam-library` | `conservar_actual` | 10.16 |
| `chained-open-then-volume` | `conservar_actual` | 10.16 |
| `historical-carter-v2-compound-smoke` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `runtime_servidor` | `conservar_actual` | 10.0 |
| `carga_descarga_modelos` | `conservar_actual` | 10.2 mide presencia; 09.5.9 no transplanta unload |
| `vram_ram_cpu` | `conservar_actual` | 10.2 |
| `latencia_llm` | `conservar_actual` | 10.2 / 10.7 |
| `arranque` | `conservar_actual` | 10.2 mide arranque; 09.5.9 conserva el vivo |
| `watchdog` | `conservar_actual` | 10.2 |
| `estabilidad` | `conservar_actual` | 10.2 idle corto, no 24 h |
| `field_ui_accesibilidad` | `conservar_actual` | 10.17 |
| `vision_camara` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `memoria_proactividad` | `conservar_actual` | 10.14 |
| `journal` | `conservar_actual` | 10.0 / 11 |
| `setup_publish` | `conservar_actual` | 10.0 |
| `privacidad` | `conservar_actual` | 10.17 |
| `seguridad` | `conservar_actual` | 10.17 |
| `diagnosticos` | `conservar_actual` | 10.2 |
| `auto_approve` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `soak-24h-as-requirement` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `residual_docs` | `conservar_actual` | recordatorio, no lote |
| `residual_code_foreign` | `rechazar` | protege 10–11 de repetir un mecanismo medido |
| `residual_code_predecessor` | `conservar_actual` | no lote |
| `residual_evidence` | `conservar_actual` | no lote; 10.1 no reparsea 09.5.4 |

Las 9.268 tarjetas de auditoría 09.5.2–09.5.4 viven en `artifacts/goal095/ledger/` y `artifacts/goal095/synthesis/09.5.9_card_assignment.v1.json`. No se copian árboles fuente, GGUF, datasets ni secretos a `biblioteca/`.
<!-- goal095-12-generated:end -->
