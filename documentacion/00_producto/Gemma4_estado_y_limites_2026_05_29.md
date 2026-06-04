# Baxy — Estado técnico y límites de hardware (2026-05-29)

> Sección para incorporar al informe **Producto, Riesgos y Competencia**. Resume el
> trabajo de la sesión y, sobre todo, **los límites reales de hardware**: qué corre
> en una GPU de 4 GB (el target), y qué haría falta para correr **sin gráfica**.

---

## 1. Qué se hizo en esta sesión

### Interfaz (reskin "Baxy field")
La GUI real es la web `ui_field` (React/Vite, servida por pywebview), **no** la PyQt
legacy. Se está re-skineando para que matchee el nuevo prototipo:
- Marco con **borde rojo viajero** (animado) y **recoloreo por estado** (idle/listening/
  thinking/speaking/standby) del núcleo, el "cromo" y las barras de métricas.
- Substrate compacto (métricas `m-*`, perfiles con íconos = modos de accesibilidad),
  split de paneles (triggers/tools a la izquierda, sessions/memory a la derecha),
  ventana **frameless** (sin barra de título del SO).
- **Aplicado (UI web)**: el reskin de `ui_field` está aplicado sobre la UI web.

### Estabilidad bajo carga de GPU
- **Crash al usar la app mientras se juega → arreglado.** Era el proceso de render
  del WebView2 cayéndose por falta de GPU (saturada por el juego). Fix: la UI
  renderiza por **CPU** (`--disable-gpu`), así no compite con el juego ni el LLM.

### Fallback a CPU cuando la GPU está ocupada (NUEVO, gated)
- Perfil **`cpu`** (`-ngl 0`): corre el LLM enteramente en CPU (**0 VRAM**, visión OFF).
- **Auto-switch**: un watcher detecta cuando un proceso ajeno (juego/render) satura la
  GPU y cambia al perfil `cpu` — **apaga el server GPU y le devuelve ~3.4 GB de VRAM al
  juego**, siguiendo en CPU. Al liberarse la GPU, vuelve a `vram4`. El cambio se aplica
  en un momento seguro (entre turnos), nunca a mitad de una respuesta.
- **Velocidad CPU medida**: ~30 tok/s de generación + ~1.400 tok/s de prefill en un CPU
  de escritorio → estimado **~12-20 tok/s en una laptop**. Usable para respuestas cortas.
- Gated (`GEMMA4_AUTO_CPU_FALLBACK`, default OFF) hasta validarlo en vivo con un juego real.

### Competidores (backlog B1–B13)
Lo adoptable y no-redundante está **hecho** (B1 recovery, B2 memory-tools, B3a streaming
TTS, B3b earcon, B5 confirmación, B6 file-processor, B7 web-fallback, B8 reminders). El
único gap estratégico pendiente es **B9 (cliente MCP)**. Detalle en `BACKLOG_competidores.md`.

---

## 2. Límites del target actual (GPU de 4 GB · perfil `vram4`)

El producto está pensado para una **laptop/PC con 4 GB de VRAM** (GTX 1650, RTX 3050 4GB).
Eso impone límites duros, todos **medidos**:

| Aspecto | Límite real | Por qué |
|---|---|---|
| **Modelo** | Solo **Gemma 4 E2B-Q4_K_M** | Es el único Gemma 4 que entra **completo** (modelo + visión residente + KV) en ≤4 GB: **3.36 GB medido**. E4B/26B no entran ni en su cuantización más baja. |
| **Tool-calling** | ~**75%** (E2B) vs ~91% (E4B) | Trade-off aceptado por entrar en 4 GB. El `forced-tool-retry` lo sube en producción. Con >4 GB se usaría E4B. |
| **Visión** | Residente, ~**1.2 GB** (mmproj) | Entra en 4 GB pero es lo más caro; en modo CPU se desactiva. |
| **Contexto** | **12288** (piso, no menos) | El system prompt arma ~4.6 K tokens en un "hola" y ~9.2 K en multi-tool; con menos contexto no entra ni un saludo. |
| **flash-attn** | **OFF** por default | Con FA on, los prompts >~10 K disparan un crash CUDA (#22527). Con FA off: estable (medido 37/37). Costo: prefill ~2× (mitigado). |
| **Voz / STT** | En **CPU** (0 VRAM) | TTS Piper + STT Parakeet (default) / Whisper (fallback) corren en CPU. No tocan la VRAM. |
| **Latencia** | ~2.2 s por acción | Tras el fix de cache-hit del summary-pass; las respuestas de info son más rápidas. |

**Riesgo conocido:** al recibir la **primera imagen** (visión) el footprint sube; en una
GPU de exactamente 4 GB el margen es chico. Por eso visión es residente y gateada.

---

## 3. Límites / requisitos del modo SIN GPU

El fallback a CPU abre la puerta a usuarios **sin gráfica dedicada** (o sin NVIDIA:
integradas Intel/AMD). A nivel de software **ya es posible**: el LLM corre en CPU (perfil
`cpu`), y STT (Parakeet) + TTS (Piper) **siempre** fueron CPU. Pero **todavía no funciona
out-of-the-box**, por dos piezas pendientes:

1. **Binario `llama-server` compatible con CPU.** El que viene bundleado (`tools/llama-cuda/`)
   es un build **solo-CUDA**: en una máquina sin GPU NVIDIA / sin driver, **no arranca**
   (le falta el runtime CUDA). Hace falta bundlear un build **CPU** o, mejor, **Vulkan**
   (que además usaría gráficas integradas Intel/AMD → cubre casi cualquier laptop). Los
   releases oficiales de llama.cpp los traen gratis.
2. **Auto-default al perfil `cpu`** cuando no se detecta GPU NVIDIA al arrancar (hoy el
   launcher arranca `vram4`, que asume CUDA).

**Caveats del modo sin GPU (honestos):**
- **Más lento**: ~12-20 tok/s estimado en laptop. Cómodo para respuestas cortas, lento
  para textos largos.
- **Sin visión** (el encoder mmproj es demasiado pesado en CPU).
- **RAM**: el modelo (~2 GB) se mapea con `mmap`, así que sus páginas son **evictables**
  bajo presión (no compite "duro" por RAM con un juego); el costo fijo real es el KV
  (~0.5-1 GB). Target de RAM: **8 GB de piso**.

**Conclusión:** con esas dos piezas, el asistente correría en **la gran mayoría de
laptops sin gráfica dedicada** — una expansión grande del público objetivo, de
"GPU de 4 GB" a "cualquier laptop razonable".

---

## 4. Pendiente (roadmap corto)

1. Terminar el reskin (match visual exacto + commit).
2. Validar el **auto CPU-fallback** en vivo con un juego real → flip a default-ON.
3. **Soporte sin GPU**: bundlear `llama-server` CPU/Vulkan + auto-default al perfil `cpu`.
4. Frugalidad de RAM en CPU (unload en idle + throttle de threads) para laptops de 8 GB.
5. **B9 (MCP)** — sprint estratégico, midiendo que no degrade el tool-calling.

> Método (regla del proyecto): cada cambio se MIDE, se implementa GATEADO (flag default-off),
> se valida EN VIVO, y recién se flippea. Nada se da por hecho sin un número contra un gate.
