# Carter v4 — Notas para futuros desarrolladores y agentes

> Si sos un agente que entró nuevo al proyecto, leé este documento primero.
> Si sos el usuario en 3 meses y olvidaste el contexto, también empezá acá.

## Estado actual del proyecto (2026-05-09)

Carter v4 es un asistente local Jarvis-style para Windows 11. 100% local, sin cloud, sin API keys. Hardware target: RTX 4060 Ti 16 GB VRAM.

### Modelo principal: **Gemma 4 E4B-UD-IQ2_M** (cambio reciente)

A partir del 2026-05-09 el modelo default de Carter es:
- **Modelo**: `gemma-4-E4B-it-UD-IQ2_M.gguf` (3.55 GB en disco, 5.13 GB VRAM cargado)
- **Backend**: llama.cpp CUDA build b9090 (`C:\llamacpp-cuda\bin\llama-server.exe`)
- **API**: OpenAI-compat `/v1/chat/completions` puerto 8080
- **Bench validation**: 55/60 (91.7%) en bench externo de 60 tests

**Antes** (hasta 2026-05-08) corría en `qwen3:4b-instruct-2507-q4_K_M` vía Ollama puerto 11434. Ese stack sigue siendo válido como fallback.

### Cómo arrancar Carter

```powershell
python Run_Carterv4.py
```

El launcher detecta si llama-server está corriendo en :8080. Si no, lo levanta como subprocess. Si no encuentra el binario o el modelo, cae automáticamente a Ollama+qwen3:4b.

Para forzar el stack viejo (qwen3:4b):
```powershell
python Run_Carterv4.py --no-gemma
```

### Audio y vision

**Audio (wake-word + voice input):** NO integrado todavía. La investigación previa (`INFORME_AUDIO_PARA_CARTER.md`) determinó que:
- Gemma 4 E4B tiene audio encoder Conformer USM nativo
- Pero el ecosistema runner-side NO está maduro (llama-server HTTP da 500 con `input_audio`, Ollama acepta pero transcribe rioplatense con calidad pobre)
- Whisper-large-v3 sigue siendo la opción correcta hasta nuevo aviso

**Vision (screenshot understanding):** NO integrado todavía. Gemma 4 lo soporta vía `mmproj-F16.gguf` que ya se carga en el llama-server. Decisión de uso pendiente de la investigación multimodal en curso.

## Stack runtime

```
Windows 11 26200
├── Python 3.10 / 3.13
├── llama.cpp b9090 CUDA → C:\llamacpp-cuda\bin\
├── Ollama 0.20.4 → fallback automático
├── Modelos GGUF → C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\
└── PaddleOCR (Tier 2 fallback en gui_universal_action)
```

## Arquitectura del agente (resumen)

```
Carter_v4/src/carter_v4/
├── agent.py              ← ReAct loop, max_depth=3, budget 25s/turn
├── prompt.py             ← CORE_PROMPT (heredado de qwen3, pendiente refactor para Gemma 4)
├── adapters/
│   ├── ollama.py         ← Adapter qwen3:4b nativo (legacy fallback)
│   ├── ollama_xml.py     ← Adapter XML-tools fallback
│   └── llamacpp.py       ← Adapter Gemma 4 (NUEVO 2026-05-09)
├── tools/                ← 57 tools propias (filesystem, GUI, web, terminal, etc.)
├── tool_retrieval.py     ← Top-K retrieval con multilingual-e5-small + 14 anchors
├── verify.py             ← Verifier estructural (frame-diff numpy + Win32)
├── verifier_orchestrator.py
├── safety.py             ← Detector destructive intent (Snowball stems)
├── mission_detector.py   ← Detección multi-step
├── memory.py             ← SQLite local
└── cli.py                ← REPL launcher
```

## Decisiones clave del proyecto (no romper)

1. **Honestidad por construcción (Valor 3 ContextoCarter)**: Carter NO puede decir "listo" sin verificación. El verifier estructural es la única autoridad de "lo que pasó".
2. **100% local**: nada de cloud, nada de SaaS, nada de API keys.
3. **Multilingüe estructural**: ES/EN/PT/DE/FR sin keyword lists per idioma. Snowball stems para destructive intent.
4. **Sin per-app hardcodes**: NO `if Steam` / `if WhatsApp`. Resolución por intención + tipo de acción + recursos del sistema.
5. **Alexa-tier latency** (Valor 2):
   - Trivial: <5s
   - Tool simple: <8s
   - App open: <15s
   - Multi-step: <20s p99
6. **Bench oficial 18×30 = 540 casos** es la fuente de verdad. Audit manual humano > bench oficial > tests automatizados.

## Lo que está pendiente (roadmap)

### Corto plazo (mientras esperamos investigaciones)
- ✅ Cleanup archivos sueltos (smoke_gemma, bench_latency, etc.)
- 🔄 Verifier rewrite: pasar de "tool ok = PASS" a "intent fulfilled = PASS"
- 🔄 Anti-eco / anti-genérico / anti-unverified post-LLM checks
- 🔄 Per-tool latency budgets en bench (pytest 60s, pip 90s, etc.)
- 🔄 Service Windows para llama-server (auto-start)

### Esperando investigación
- ⏳ Investigación de optimización Gemma 4 (sampling, stops, CORE_PROMPT, llama-server flags)
- ⏳ Investigación multimodal (audio nativo, vision uses, single-turn combo)

### Identificado pero NO ejecutar todavía
- 📋 Re-correr bench oficial 540 con Gemma 4 (smoke validation ≠ full bench)
- 📋 Stage 1 defensive layer del reporte Opus (filtrar qué % aplica con Gemma 4 antes de aplicar 800 LOC)

## Documentos clave a leer (en este orden)

1. **`ContextoCarter.md`** — los 25 valores no-negociables del proyecto
2. **`GEMMA4_INTEGRACION_DONE.md`** — integración Gemma 4 (lo que se hizo el 2026-05-09)
3. **`INFORME_AUDIO_PARA_CARTER.md`** — análisis de 4 caminos para audio multimodal
4. **`evidencia pruebas gemma4/REPORTE_EXTENDIDO.md`** — bench 60 tests × 21 modelos, decisión de quant
5. **`PROMPT_INVESTIGACION_FAILS_RESIDUALES_V20.md`** — los 16 patrones residuales (A-P)
6. **`investigaciones/investigacionesopus/compass_artifact_*.md`** — 2 reportes Opus con Stage 1 defensive layer (800 LOC)

## Comandos útiles

```powershell
# Arrancar Carter (Gemma 4 default)
python Run_Carterv4.py

# Arrancar Carter con qwen3:4b (legacy)
python Run_Carterv4.py --no-gemma

# Smoke test del adapter Gemma 4
cd Carter_v4 && python scripts/smoke_gemma.py

# Minimum test 10 prompts del Contrato
cd Carter_v4 && python scripts/minimum_test_gemma.py

# Bench oficial 540 casos (warning: >2h)
cd Carter_v4 && python audit/full_matrix_runner.py

# Verificar VRAM en uso
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader

# Apagar llama-server (libera 5 GB VRAM)
# Ctrl+C en la terminal donde corre, o:
Get-Process llama-server | Stop-Process
```

## Convenciones de naming

- **Gemma 4** (en este repo) = el modelo `gemma-4-E4B-it-UD-IQ2_M.gguf` de Unsloth. Confirmado por `projector: gemma4a` en logs de llama-server. NO confundir con Gemma 3n (familia distinta de Google).
- **qwen3** = `qwen3:4b-instruct-2507-q4_K_M` vía Ollama. Stack legacy fallback.
- **Tier 0/1/2** (en `gui_universal_action`) = niveles de fallback: deeplink → UIA+click → OCR.
- **Patrones A-P** = los 16 patrones residuales identificados en el audit manual de los 540 casos.

## Si algo se rompe

1. Verificá que llama-server está corriendo: `curl http://127.0.0.1:8080/health`
2. Verificá VRAM disponible: `nvidia-smi`
3. Si VRAM saturada, descargá Ollama: `curl -X POST http://127.0.0.1:11434/api/generate -d '{"model":"<modelo>","keep_alive":0}'`
4. Como último recurso, usá `--no-gemma` para volver a qwen3:4b
5. Logs del llama-server: stdout/stderr del subprocess. Si arrancaste con `Run_Carterv4.py` van a `DEVNULL` (pendiente: redirigir a archivo).

## Contacto / contexto

- Repo: local, sin remote configurado a la fecha
- Branch: `Refactorizacion`
- Owner: usuario único (usuario)
- Última sesión Claude: 2026-05-09
