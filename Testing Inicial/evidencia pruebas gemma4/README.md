# Evidencia validación Gemma 4 para Carter v4

Paquete autocontenido de evidencia para que el agente Carter decida la migración de `qwen3:4b` a Gemma 4. Generado el 2026-05-09 desde el repo `Probando Gemma 4`.

---

## Léeme primero

Si solo vas a leer un archivo, leé **[REPORTE_EXTENDIDO.md](REPORTE_EXTENDIDO.md)** — contiene TL;DR, las 4 tablas obligatorias, análisis por bloque y veredicto final.

Si querés contexto completo, ese es el orden:

1. **[Contrato.md](Contrato.md)** — el contrato original que Gemma 4 debe cumplir (10 capacidades innegociables).
2. **[GEMMA4_VALIDACION_COMPLETA.md](GEMMA4_VALIDACION_COMPLETA.md)** — el documento autoritativo que define los 60 tests del bench extendido.
3. **[REPORTE.md](REPORTE.md)** — fase 1 del bench (10 tests originales, 9/10 PASS).
4. **[REPORTE_EXTENDIDO.md](REPORTE_EXTENDIDO.md)** ⭐ — fase 2, el reporte definitivo con la decisión.
5. **[INFORME_AUDIO_PARA_CARTER.md](INFORME_AUDIO_PARA_CARTER.md)** — análisis específico del estado de audio multimodal (4 caminos posibles).

---

## Veredicto

**Modelo ganador:** `gemma-4-E4B-it-Q6_K` (6.59 GB en disco, 7.1 GB VRAM cargado).
**Score:** 57/60 (95%) vs qwen3:4b 55/60 (91.6%).
**Decisión:** **MIGRAR CONDICIONAL** — 4 de 5 criterios cumplidos, latencia multi-step p99 27s viola Alexa-tier.

Detalles completos en [REPORTE_EXTENDIDO.md](REPORTE_EXTENDIDO.md).

---

## Contenido de esta carpeta

```
evidencia pruebas gemma4/
├── README.md                          (este archivo)
├── REPORTE_EXTENDIDO.md               ⭐ reporte principal (fase 2)
├── REPORTE.md                         reporte fase 1 (10 tests)
├── INFORME_AUDIO_PARA_CARTER.md       audio multimodal: 4 caminos
├── Contrato.md                        contrato original 10 capacidades
├── GEMMA4_VALIDACION_COMPLETA.md      documento autoritativo de validación
│
├── harness/                           código Python del benchmark
│   ├── tests.py                       SYSTEM_PROMPT + 10 tests fase 1
│   ├── tests_extended.py              60 tests fase 2 (A30 + B20 + C10)
│   ├── tools.py                       9 stubs deterministas base
│   ├── tools_extended.py              12 stubs adicionales para Bloque B
│   ├── run_bench.py                   runner fase 1
│   ├── run_bench_extended.py          runner fase 2
│   ├── run_baseline_qwen.py           runner contra Ollama qwen3:4b
│   ├── audio_full.py                  Bloque D (Ollama + mtmd-cli)
│   ├── audio_probes.py                Bloque D inicial (solo mtmd-cli)
│   ├── probe_ollama_audio.py          verificación de soporte audio Ollama
│   ├── judge.py                       juez automatizado PASS/FAIL
│   └── bench_all.ps1                  orquestador 21 modelos
│
├── samples/                           5 audios TTS español-MX (16kHz mono)
│   ├── audio_01_hora.wav              "qué hora es"
│   ├── audio_02_negation.wav          "no abras Spotify, solo decime si está instalado"
│   ├── audio_03_multistep.wav         "abrí Notepad y escribí hola mundo"
│   ├── audio_04_phonetic.wav          "abrí stim" (mispronounced)
│   ├── audio_05_codeswitch.wav        "dame el time y abrí Spotify por favor"
│   └── generate_audio.ps1             script para regenerar más samples
│
└── results/                           datos crudos del bench
    ├── judged.json                    matriz PASS/FAIL completa por modelo
    ├── summary.json                   stats agregadas (totales + percentiles)
    ├── vram_log.csv                   VRAM real medida con nvidia-smi
    ├── baseline_qwen3-4b.json         60 tests sobre qwen3:4b (Ollama)
    ├── audio_E4B.json                 5 audios × 2 prompts (Ollama + mtmd)
    ├── trazas_modelos/                trazas completas de los 22 modelos
    │   ├── extended_E4B-Q6_K.json     ⭐ ganador
    │   ├── extended_E4B-Q4_K_M.json
    │   ├── extended_E4B-Q5_K_M.json
    │   ├── ... (22 archivos en total)
    │   └── extended_31B-Q3_K_M.json
    └── logs_servidores/               stdout/stderr de cada llama-server
        ├── server_<modelo>.log
        └── server_<modelo>.log.err
```

---

## Cómo reproducir el bench

Hardware necesario: **NVIDIA RTX 4060 Ti 16 GB** (idéntico al target Carter) o equivalente.

Software necesario:
- **llama.cpp build CUDA** (probado con b9090 CUDA 13.1 — ver anexos del REPORTE_EXTENDIDO).
- **Ollama 0.20.4** con `qwen3:4b-instruct-2507-q4_K_M` y `gemma4:e4b` instalados.
- **Python 3.10+**.
- **Modelos GGUF Gemma 4** descargados de `unsloth/gemma-4-*-it-GGUF` en HuggingFace (no incluidos en esta carpeta — pesan 335 GB).

Comandos:

```powershell
# 1. Levantar llama-server con el modelo ganador
& "C:\llamacpp-cuda\bin\llama-server.exe" `
    -m "models\E4B\gemma-4-E4B-it-Q6_K.gguf" `
    --mmproj "models\E4B\mmproj-F16.gguf" `
    --jinja --port 8080 -ngl 99 -c 16384

# 2. En otra terminal, correr el bench extendido sobre ese modelo
python harness\run_bench_extended.py E4B-Q6_K

# 3. Para baseline
python harness\run_baseline_qwen.py

# 4. Para audio
python harness\audio_full.py

# 5. Para juzgar todo
python harness\judge.py
```

Para correr los 21 modelos de una pasada: `powershell -ExecutionPolicy Bypass -File harness\bench_all.ps1` (~3 horas en RTX 4060 Ti CUDA).

---

## Criterios de PASS aplicados

Todos los tests se juzgaron con **honestidad por construcción**: un test pasa solo si la **intención del usuario se cumple verificablemente**. "Llamó la tool X" no es PASS si la tool fue llamada con argumentos basura o si el modelo después alucinó el contenido. Reglas idénticas al Contrato original.

El juez automatizado está en [harness/judge.py](harness/judge.py) — cada test tiene un criterio explícito en código revisable.

---

## Limitaciones conocidas

1. **Bug CUDA llama.cpp b9090** afecta cuantizaciones agresivas. 3 modelos crashearon a mitad del bench:
   - 26B-A4B-UD-IQ2_XXS (al 50%)
   - 31B-Q3_K_M (al 87%)
   - E2B-Q5_K_M (al 33%, retry exitoso después)
   El modelo recomendado E4B-Q6_K **no sufrió crashes** en mi corrida.

2. **mtmd-cli** devolvió texto vacío en el Bloque D — bug del flag o captura de output. Los datos relevantes están en Ollama (que sí funcionó para audio).

3. **Audio en español rioplatense:** las 5 muestras son TTS sintético español-MX (Microsoft Sabina), no español argentino humano real. La calidad de transcripción puede ser distinta con voces argentinas reales.

4. **Discrepancia con audit Carter:** qwen3:4b sacó 91.6% en este bench vs 61% PASS REAL del audit 540 casos. Sugerencia: re-ejecutar el bench oficial 540 con Gemma 4 antes de comprometerse a migrar, para evitar sorpresas.

---

## Próximos pasos sugeridos (para el agente Carter)

Si la decisión es **migrar**:

1. Validar el bench oficial 540 con Gemma 4 + Stage 1 fixes.
2. Adaptar `agent.py` de Carter para hablar OpenAI-API contra `llama-server --jinja` (ya es OpenAI-compat, mínimo rework).
3. Mantener Whisper para audio (Bloque D no compite con Whisper en es-AR).
4. Plan de rollback: el endpoint Ollama queda intacto, basta cambiar URL.

Si la decisión es **NO migrar**:

1. Continuar con Plan A (defensive layer 800 LOC sobre qwen3:4b).
2. Re-evaluar Gemma 4 en 3-6 meses cuando: (a) Google fine-tunee a más idiomas, (b) llama.cpp CUDA estabilice, (c) llama-server agregue audio nativo.

Si la decisión es **CONDICIONAL** (lo que recomienda el reporte):

1. Decidir si la latencia multi-step p99 27s es deal-breaker.
2. Decidir si +3 puntos de patrón A justifican el cambio de stack.
3. Considerar piloto: usar Gemma 4 en el 10% del tráfico, comparar telemetría real.

---

## Contacto

Generado por el agente del repo `Probando Gemma 4`. Cualquier duda sobre datos crudos o reproducibilidad: mirar [harness/](harness/) y [results/](results/).
