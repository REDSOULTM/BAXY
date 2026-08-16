# Documentación — Baxy (antes Gemma 4 Agent, brevemente Carter)

Puerta de entrada a toda la documentación del proyecto. **Asistente de voz
local para Windows** sobre **Gemma 4 E2B-FT** (GGUF Q4_K_M), corriendo en
laptops/PCs modestas (target: 4 GB de VRAM, perfil `vram4`, ctx 12288).

> **Fuente de verdad del ESTADO del proyecto:**
> [`_backlog/BACKLOG_MAESTRO.md`](_backlog/BACKLOG_MAESTRO.md).
> Consolida todos los backlogs históricos con el estado de cada ítem
> **verificado contra el código real**. Si dudás de qué está hecho y qué no,
> empezá ahí, no por los planes individuales (que pueden estar desactualizados).

---

## Cómo está organizada

Las carpetas numeradas `00`–`11` son **documentación vigente**, una por
subsistema. Cada una (las grandes) tiene su propio `README.md` con el estado
del subsistema y un mapa de sus documentos. Las carpetas con prefijo `_` son
auxiliares:

- **`_backlog/`** — el backlog maestro (la verdad del estado).
- **`_historico/`** — **archivo de proceso**: sprints viejos, auditorías
  baseline, benchmarks, handoffs y crash-logs ya superados. **NO refleja el
  estado actual.** Se conserva por trazabilidad, no se mantiene al día. Ver
  [`_historico/README.md`](_historico/README.md).

Dentro de varias carpetas hay una subcarpeta `research/` con la investigación
recibida o propia que respaldó las decisiones. Es material de soporte; algunos
documentos son históricos (lo avisan en su cabecera).

---

## Mapa de carpetas

| Carpeta | Qué contiene |
|---------|--------------|
| [`00_producto/`](00_producto/) | Estado y límites del producto, competencia, licencias OSS, capas de computer-use, modos de accesibilidad, decisiones (ADRs), branching. |
| [`01_arquitectura/`](01_arquitectura/) | Arquitectura del sistema, auditoría arquitectural, mapa de descomposición de archivos-dios, MCP conectado, diagramas delta. |
| [`02_router/`](02_router/) | Router de selección de tools: pipeline, componentes, gates/config, eval y métricas, historial de sprints, plan maestro. |
| [`03_voz_stt/`](03_voz_stt/) | Voz: STT (Whisper int8 CPU / Parakeet), wake-word (LiveKit), TTS (Piper). |
| [`04_computer_use/`](04_computer_use/) | Control del SO por voz: mission planner/executor, perfil vram4 único + modos de accesibilidad, playback streaming. |
| [`05_vision_camara/`](05_vision_camara/) | Control manos-libres por cámara/gestos (MediaPipe): POC, control de ventanas, reportes. |
| [`06_vram_estabilidad/`](06_vram_estabilidad/) | Arquitectura para 6 GB / target 4 GB, estabilidad bajo carga de GPU, resolución del crash CUDA #22527. |
| [`07_latencia/`](07_latencia/) | Optimización de latencia: tokens del prompt, cache-hit del prefill, thinking. |
| [`08_memoria_jarvis/`](08_memoria_jarvis/) | Memoria y capa "Jarvis": observador de ambiente, perfil de gustos, skills/subagents. |
| `09_finetune/` | Fine-tune del modelo (E2B-FT). *Carpeta reservada, aún vacía.* |
| [`10_auditorias/`](10_auditorias/) | Auditorías: flags, comparación con Carter OS (proyecto de referencia externo). |
| [`11_research_recibido/`](11_research_recibido/) | Investigaciones externas recibidas (sin procesar). |
| [`_backlog/`](_backlog/) | **`BACKLOG_MAESTRO.md` — fuente de verdad del estado.** |
| [`_historico/`](_historico/) | Archivo de proceso (sprints, baselines, benchmarks). **No es el estado actual.** |

---

## Datos rápidos del proyecto (estado vigente — 2026-06-09)

- **Modelo:** Gemma 4 E2B-FT (GGUF Q4_K_M), fine-tune local.
- **Contexto:** 12288 tokens (perfil `vram4`, único perfil real).
- **VRAM target:** 4 GB. **Visión (mmproj) RESIDENTE por default** (`GEMMA4_VISION_ALWAYS=1`):
  medido que NO penaliza el cache de texto (llama.cpp #21133) y evita la carga
  on-demand de la imagen; toggle en settings para volver al lazy. Fallback CPU gated.
- **UI:** web (`ui_field`, React + pywebview). La GUI PyQt6 vieja fue **eliminada**.
- **Voz:** STT Whisper int8 CPU (Parakeet por flag), wake-word LiveKit, TTS Piper
  streaming. Mic **WASAPI** + resample a 16k + auto-calibración de ruido relativa.
  Todo en CPU (0 VRAM).
- **Idioma:** **selector en settings** (`GEMMA4_VOICE_LANG`; "" = Automático) que fija
  todo el stack; reparación universal de mismatch de idioma del reply.
- **Router:** `gemma4_agent/routing/planner.py` (encoder FT + abstain head + per-tool
  head + Tool2Vec). Familia de **guardas de honestidad** estructurales default-ON
  (cacería 6162 cerrada). Resolución de sitios "ve a X" por señal estructural +
  popularidad + DNS (sin lista hardcoded).
- **Regla de oro (CLAUDE.md):** nada se da por hecho sin un número contra un gate; el
  LLM responde (sin enlatados); todo OSS y gratis; universal (multi-idioma/acento).

> **El changelog detallado del 2026-06-03 → 2026-06-09 está en
> [`_backlog/BACKLOG_MAESTRO.md`](_backlog/BACKLOG_MAESTRO.md) §9–§16.**
