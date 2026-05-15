# Probando Gemma 4

Validación exhaustiva de **Gemma 4** como reemplazo de `qwen3:4b` en el proyecto **Carter** (asistente local Windows).

> **Modelo ganador:** `gemma-4-E4B-it-Q6_K` con **540/540 = 100%** en bench oficial Carter.
> **VRAM:** 7.1 GB · **Hardware target:** RTX 4060 Ti 16 GB CUDA.

---

## 🚀 Empezar acá

| Si querés... | Andá a |
|---|---|
| **El reporte definitivo final** ⭐ | [docs/REPORTE_GEMMA4_PARA_CARTER.md](docs/REPORTE_GEMMA4_PARA_CARTER.md) |
| **Ver todo el proyecto navegable + 16 gráficos** | [documentacion/INDEX.md](documentacion/INDEX.md) |
| **El paquete entregable al agente Carter** | [evidencia pruebas gemma4/](evidencia%20pruebas%20gemma4/) |
| **Probar el modelo conversacionalmente** | `python chat_gemma.py` |
| **Probar el modelo con tools REALES Windows** | `python chat_carter.py` |

---

## 📂 Estructura del repo

```
Probando Gemma 4/
│
├── README.md                    ← este archivo
├── .gitignore
│
├── chat_gemma.py                Chat conversacional simple sin tools (con --image)
├── chat_carter.py               Chat con 15 tools REALES Windows (no stubs)
│
├── docs/                        Documentos largos del proyecto
│   ├── REPORTE_GEMMA4_PARA_CARTER.md   ⭐ definitivo final (30 valores Carter)
│   ├── REPORTE.md                       Fase 1 (10 tests inicial)
│   ├── REPORTE_EXTENDIDO.md             Fase 2 (60 tests × 22 modelos)
│   ├── GEMMA4_VALIDACION_COMPLETA.md    Doc autoritativo del bench Fase 2
│   ├── INFORME_AUDIO_PARA_CARTER.md     Audio nativo Gemma 4 vs Whisper
│   ├── Contrato.md                      Contrato original (10 capacidades)
│   └── ContextoCarter.md                30 valores Carter v4/v5
│
├── documentacion/               Documentación visual y trackeable del proyecto
│   ├── INDEX.md                 Índice maestro con cronología completa
│   ├── 01_resumen_ejecutivo/    ... 10_carter_integration/    (10 secciones)
│   ├── graficos/                16 PNG comparativos (matplotlib)
│   ├── datos_crudos/            JSON + CSV originales referenciados
│   └── generar_graficos.py      Regenera los 16 PNG
│
├── evidencia pruebas gemma4/    Paquete autocontenido entregable al agente Carter
│   ├── README.md
│   ├── REPORTE_*.md (copias)
│   ├── harness/, results/, samples/
│
├── harness/                     Fase 1 + Fase 2 (10 + 60 tests)
│   ├── tests.py, tests_extended.py
│   ├── tools.py, tools_extended.py
│   ├── run_bench.py, run_bench_extended.py
│   ├── run_baseline_qwen.py
│   ├── audio_full.py, audio_probes.py
│   └── judge.py
│
├── harness_carter540/           Fase 3 — bench oficial Carter 540 casos
│   ├── REPORTE_540_GEMMA4.md
│   ├── tests_540.md, system_prompt.py, auditor.py
│   ├── run_bench.py, run_bench_consolidated.py
│   ├── tool_schemas.json (60), tool_schemas_consolidated.json (16)
│   └── results/                 v1 → v14 individual + v1 → v6 consolidated
│
├── results/                     Fase 1 + Fase 2 outputs (22 modelos × 60 tests)
│   ├── extended_*.json
│   ├── server_*.log (gitignored)
│   ├── audio_E4B.json
│   ├── baseline_qwen3-4b.json
│   ├── judged.json, summary.json
│   └── vram_log.csv
│
├── samples/                     5 .wav TTS español-MX para Bloque D audio
│
├── scripts/                     Scripts auxiliares
│   ├── watch.py                 Live watcher de benches en curso
│   └── download_all.ps1         Descarga las 22 cuantizaciones
│
└── models/                      GGUF descargados ~335 GB (gitignored)
```

---

## 🎯 Resumen ejecutivo

- **3 fases** de bench: 10 tests → 60 tests × 22 quants → 540 casos Carter
- **5,800+ invocaciones** al modelo registradas
- **22 cuantizaciones** evaluadas (E2B, E4B, 26B-A4B, 31B)
- **14 iteraciones** del bench Carter 540 hasta llegar al 540/540
- **16 gráficos** comparativos generados con matplotlib
- **40+ fuentes oficiales** citadas (Google, llama.cpp, Anthropic)
- **30 valores Carter** mapeados a evidencia medida

Detalle completo, navegable y trackeable: [documentacion/INDEX.md](documentacion/INDEX.md).

---

## 🛠️ Comandos rápidos

```powershell
# Levantar el modelo ganador (E4B-Q6_K) con llama-server CUDA
& "C:\llamacpp-cuda\bin\llama-server.exe" `
    -m "models\E4B\gemma-4-E4B-it-Q6_K.gguf" `
    --mmproj "models\E4B\mmproj-F16.gguf" `
    --jinja --port 8080 -ngl 99 -c 16384 `
    --parallel 1 --ctx-checkpoints 1 --flash-attn on

# Chat interactivo
python chat_gemma.py
python chat_carter.py

# Re-correr bench Carter 540
python harness_carter540\run_bench.py

# Ver progreso de bench en vivo
python scripts\watch.py

# Regenerar gráficos
python documentacion\generar_graficos.py
```

---

## 📦 Estado final

- [x] 540/540 medido y reproducible con E4B-Q6_K
- [x] 540/540 reproducible con 16 composite tools
- [x] VRAM medida para 22 cuantizaciones
- [x] Latencia p50/p90/p99 medida en CUDA
- [x] Comparativa vs qwen3:4b (modelo Carter actual)
- [x] Audio Bloque D ejecutado y documentado (Whisper sigue ganando)
- [x] 30 valores Carter mapeados a evidencia
- [x] 40+ fuentes oficiales citadas
- [x] Paquete entregable agente Carter
- [x] 16 gráficos comparativos generados
- [x] Documentación visual y trackeable

**Misión cumplida.** El próximo paso lo hace el agente Carter en su repo.
