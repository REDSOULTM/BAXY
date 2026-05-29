"""Genera el informe Word del PRODUCTO TERMINADO (no el estado de sesión):
Gemma 4 Agent — Producto, Riesgos y Competencia (v2).

Cubre: resumen del producto, tecnologías usadas, diagrama de cómo funciona todo,
tabla de competidores, y riesgos + mitigaciones. Usa python-docx (ya instalado:
la app genera .docx). Crea un archivo NUEVO, no toca el que esté abierto.

Uso:  python scripts/_gen_informe_producto_v2.py
Salida: Gemma4_Agent_Producto_Riesgos_y_Competencia_v2.docx (en la raíz del repo)
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Gemma4_Agent_Producto_Riesgos_y_Competencia_v2.docx"

doc = Document()

# --- estilo base ---
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)


def h(text, level=1):
    doc.add_heading(text, level=level)


def p(text, *, italic=False, bold=False):
    par = doc.add_paragraph()
    run = par.add_run(text)
    run.italic = italic
    run.bold = bold
    return par


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for i, htxt in enumerate(headers):
        hdr[i].text = ""
        r = hdr[i].paragraphs[0].add_run(htxt)
        r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    return t


def mono_block(text):
    """Bloque monoespaciado (para el diagrama ASCII)."""
    par = doc.add_paragraph()
    run = par.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(7.5)
    return par


# ====================== PORTADA ======================
title = doc.add_heading("Gemma 4 Agent", level=0)
sub = doc.add_paragraph()
r = sub.add_run("Producto, Riesgos y Competencia")
r.bold = True
r.font.size = Pt(14)
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run("Asistente de IA personal · local · privado · por voz").italic = True

# ====================== 1. RESUMEN ======================
h("1. El producto en una frase", 1)
p("Gemma 4 Agent es un asistente de IA personal que corre 100% en la máquina del "
  "usuario — sin nube, sin cuotas, sin telemetría. Funciona por voz (multilingüe), "
  "ve y opera el escritorio, gestiona archivos y la web, y está diseñado para "
  "hardware modesto: entra en una GPU de 4 GB de VRAM y puede correr incluso SIN "
  "gráfica dedicada (en CPU). El modelo de lenguaje decide qué hacer (no hay árboles "
  "de if/else ni respuestas enlatadas) y NO miente: cada acción se verifica contra el "
  "estado real del sistema operativo.")

h("Diferenciadores (el \"moat\")", 2)
for b in [
    "100% local + OSS/gratis: privacidad, costo cero y funciona offline.",
    "Voz-first y multilingüe por embeddings (no listas de palabras por idioma).",
    "Honestidad estructural: verifica por ESTADO del SO, no confía en un \"juez\" LLM que alucina.",
    "Hardware modesto: 4 GB de VRAM, y un camino para correr sin GPU.",
    "Accesibilidad real (WCAG 2.1/2.2): modos \"no vidente\" (narra todo, lee la pantalla) y \"movilidad\" (100% por voz, manos libres) — el agente hace las cosas POR el usuario.",
    "El LLM decide; las únicas piezas deterministas son guardas estructurales y resolución por estado del SO.",
]:
    doc.add_paragraph(b, style="List Bullet")

# ====================== 2. ACCESIBILIDAD ======================
h("2. Modos de accesibilidad (diseño inclusivo)", 1)
p("Gemma 4 Agent no es solo un asistente \"manos libres\": HACE las cosas POR el "
  "usuario, con tres modos respaldados por las pautas WCAG 2.1/2.2. El comportamiento "
  "se modula por instrucciones al modelo (multilingüe, sin frases enlatadas) MÁS "
  "garantías ESTRUCTURALES que impone el runtime — no dependen de que el modelo "
  "\"se acuerde\" de comportarse bien.")
table(
    ["Modo", "Para quién", "Qué garantiza el sistema"],
    [
        ["Normal", "Uso general", "Comportamiento base, sin ajustes de accesibilidad."],
        ["No vidente", "Personas ciegas o de baja visión (necesidad perceptual)",
         "Todo por audio: NARRA cada acción ejecutada, LEE la pantalla a pedido, y DESCRIBE errores y diálogos visuales. Respuestas descriptivas, nunca un \"listo\" seco."],
        ["Movilidad reducida", "Discapacidad motriz (necesidad motora)",
         "Control 100% por voz, MANOS LIBRES: el agente NUNCA le pide al usuario tocar teclado o mouse — completa la tarea él mismo; confirma por voz lo irreversible; ve la pantalla."],
    ],
)
p("Los modos se activan por VOZ (capa semántica multilingüe), persisten entre sesiones "
  "y se combinan con cualquier motor de hardware (CPU o GPU). Es un diferenciador poco "
  "común: entre los asistentes locales de voz que revisamos no encontramos garantías de "
  "accesibilidad estructurales equivalentes.", italic=True)

# ====================== 3. TECNOLOGIAS ======================
h("3. Tecnologías usadas", 1)
table(
    ["Capa", "Tecnología", "Rol / por qué"],
    [
        ["LLM", "Gemma 4 E2B (Q4_K_M) vía llama.cpp / llama-server", "El cerebro. Cuantizado a 4 bits para entrar en ≤4 GB. OSS, intercambiable, sin lock-in."],
        ["Transcripción (STT)", "Parakeet-TDT-0.6b-v3 (sherpa-onnx, int8) · Whisper de respaldo", "Voz→texto en CPU (0 VRAM), rápido (~74 ms) y multilingüe."],
        ["Voz (TTS)", "Piper VITS (es_MX-claude), CPU", "Texto→voz neural local, baja latencia, sin nube."],
        ["Wake / VAD", "Wake-word LiveKit (ONNX) + detección de voz", "Activación por \"hey gemma\" sin enviar audio a ningún lado."],
        ["Ruteo / intención", "sentence-transformers (MiniLM, embeddings multilingües)", "Elige qué herramientas ofrecer al LLM por significado, no por keywords."],
        ["Visión", "Encoder multimodal de Gemma 4 (mmproj)", "Entiende la pantalla/imágenes. Residente y gateada por presupuesto de VRAM."],
        ["Computer-use", "UI Automation (UIA) → OCR (Tesseract) → visión, verify por dHash", "Opera apps reales con una cascada robusta y verificación visual."],
        ["Interfaz", "React + Vite servida por pywebview · backend FastAPI + WebSocket", "Ventana nativa de escritorio; eventos en vivo (estado, log, métricas, grafo)."],
        ["Gestión de hardware", "Perfiles (vram4/cpu/standby) + watcher con nvidia-smi", "Adapta el motor a la GPU disponible y a la carga (juego/app pesada)."],
        ["Memoria / contexto", "Compaction con resumen + memoria de experiencia (MiniLM)", "Acota el prompt (~7-12k) y reusa patrones exitosos. Todo local."],
    ],
)

# ====================== 3. DIAGRAMA ======================
h("4. Cómo funciona todo (flujo de un turno de voz)", 1)
DIAG = r"""
   [ Microfono ]
        |  audio
        v
   VAD --> Wake word ("hey gemma") --> STT  (Parakeet, sherpa-onnx, CPU)
                                         |  texto transcripto
                                         v
  +========================= AGENTE (Gemma4Agent) ==========================+
  |                                                                         |
  |   Router (MiniLM) ----> Planner (elige un SUBSET de herramientas)       |
  |        ^                              |                                 |
  |   Memoria + Contexto                  v                                 |
  |   (compaction + experience)   LLM  Gemma 4 E2B-Q4  (llama-server)       |
  |                                       |  tool_calls                     |
  |                                       v                                 |
  |                            Herramientas (domain_tools/):                |
  |                            archivos . web . apps . media .              |
  |                            vision . computer-use (UIA/OCR) . ...        |
  |                                       |  resultados                     |
  |                                       v                                 |
  |       Guardas: verify por ESTADO DEL SO (tristate, "no miente")         |
  |       --> confirma / reintenta (error-recovery) / pide confirmacion     |
  +=========================================================================+
                                         |  respuesta (texto)
                                         v
                                  TTS (Piper, CPU)  -->  [ Parlante ]

  -------------------------------------------------------------------------
  CAPA DE HARDWARE  (llama-server / llama.cpp):
     perfil vram4   (GPU, -ngl 99, vision ON)    <- default con GPU NVIDIA
     perfil cpu     (-ngl 0, 0 VRAM, vision OFF) <- GPU ocupada / sin GPU
     perfil standby (server apagado)
     Watcher (nvidia-smi): GPU saturada por un juego -> pasa a CPU -> libera VRAM
  -------------------------------------------------------------------------
  INTERFAZ:  React (ui_field) <-> pywebview <-> FastAPI + WebSocket
             eventos en vivo: estado, log de actividad, metricas, grafo neuronal
"""
mono_block(DIAG.strip("\n"))
p("Todo el recorrido (escuchar → entender → razonar → actuar → verificar → hablar) "
  "ocurre en la máquina del usuario. La capa de hardware elige el motor según los "
  "recursos: con GPU NVIDIA usa la GPU; si la GPU está ocupada (un juego) o no hay "
  "GPU, el mismo modelo corre en CPU.", italic=True)

h("El modo CPU en detalle — qué cambia frente al perfil GPU (vram4)", 2)
p("El modo CPU NO es una versión recortada del cerebro: responde con la MISMA calidad "
  "porque es el MISMO modelo y los mismos pesos. Lo que cambia es la VELOCIDAD y la "
  "VISIÓN. Es un fallback para no quedarte sin asistente cuando un juego ocupa la GPU "
  "(o si no tenés GPU dedicada), no un reemplazo de igual rendimiento.")
table(
    ["Aspecto", "Perfil vram4 (GPU)", "Perfil cpu"],
    [
        ["Dónde corre el LLM", "GPU NVIDIA (-ngl 99)", "CPU (-ngl 0) · 0 VRAM"],
        ["Visión (ver pantalla / imágenes)", "SÍ — mmproj residente", "NO — desactivada"],
        ["Calidad del texto / decisiones", "(referencia)", "IDÉNTICA: mismo modelo y pesos"],
        ["Velocidad de respuesta (decode)", "Camino rápido por defecto", "~20 tok/s en CPU de escritorio (techo); una laptop de 4 GB: bastante menos"],
        ["Costo del 1er turno (prefill)", "Bajo", "~2.4 s para un prompt de ~2.8k tokens (luego se cachea)"],
        ["Memoria que usa el modelo", "VRAM de la GPU", "RAM del sistema (mmap, páginas evictables)"],
        ["Computer-use", "cascada UIA → OCR → visión", "UIA → OCR (sin el escalón de visión)"],
        ["Cuándo se usa", "Default con GPU NVIDIA libre", "GPU ocupada (juego) o sin GPU dedicada"],
    ],
)
p("En números MEDIDOS (en el CPU de escritorio del desarrollador, que es un TECHO): la "
  "generación va a ~20 tokens/s y una respuesta de ~80 tokens sale en ~4 s; procesar un "
  "prompt largo (~2.8k tokens) cuesta ~2.4 s la primera vez. En una laptop típica de 4 GB "
  "el decode será del orden de unos pocos tokens/s, así que una respuesta puede tardar "
  "~5-15 s (estimado, no medido en ese hardware). Resumen honesto: en CPU el asistente "
  "PIENSA igual, pero RESPONDE más lento y NO VE la pantalla.", italic=True)

# ====================== 4. COMPETIDORES ======================
h("5. Panorama competitivo", 1)
p("Revisamos el espacio (fuentes verificadas, ver enlaces al final) en dos planos: "
  "(A) asistentes personales / de voz LOCALES —el terreno propio de Gemma 4 Agent— y "
  "(B) agentes de computer-use y frameworks de orquestación, adyacentes pero con otro "
  "objetivo. Conclusión honesta y sin adornos: Gemma 4 Agent NO es \"el único asistente "
  "local por voz\". Existe un ecosistema activo, e incluso un clon tipo Jarvis "
  "(isair/jarvis) que también corre sobre Gemma con LLM local. Lo que nos diferencia no "
  "es \"ser local\", sino la COMBINACIÓN de cuatro ejes que ningún proyecto revisado "
  "reúne a la vez:")
for b in [
    "Un LLM local que DECIDE el camino (no listas de intents fijos).",
    "Computer-use de escritorio GENÉRICO: opera cualquier app vía UIA → OCR → visión "
    "(no solo Chrome ni solo domótica).",
    "Verificación de cada acción por ESTADO del sistema operativo (\"no miente\").",
    "Entra en 4 GB de VRAM (el rival más cercano, isair/jarvis —también Gemma—, pide 8 GB+).",
]:
    doc.add_paragraph(b, style="List Bullet")

h("A. Asistentes personales / de voz LOCALES (los comparables reales)", 2)
table(
    ["Proyecto", "Qué es", "Local · LLM", "Computer-use", "Diferencia con Gemma 4 Agent"],
    [
        ["isair/jarvis", "Asistente de voz local tipo Jarvis", "Local; LLM local vía Ollama (default gemma4:e2b)",
         "Parcial: lee pantalla (OCR), controla Chrome, MCP", "El más cercano. Pide 8 GB+ VRAM (vs 4) y su control se limita a Chrome, no a apps arbitrarias."],
        ["dnhkng/GLaDOS", "Asistente con personalidad + visión + memoria", "Local (MIT); LLM local (Ollama) + visión",
         "No (conversa, ve cámara, tools MCP)", "No opera apps de escritorio (no clic/teclado)."],
        ["Home Assistant — Assist", "Asistente de voz para domótica", "Local; intents fijos + LLM local opcional (Ollama)",
         "No (controla dispositivos del hogar)", "Domótica, no escritorio; el LLM es opcional y no decide el flujo."],
        ["Mycroft / OpenVoiceOS", "Asistente de voz por skills (Mycroft cerró 2023; OVOS continúa)", "Local; skills/intents + LLM local opcional",
         "No", "Skills/intents clásicos; sin computer-use."],
        ["Leon AI", "Asistente personal open-source (MIT)", "Local; agéntico (v2), IA local o remota",
         "No (skills/acciones, no UI de escritorio)", "Sin computer-use de escritorio."],
        ["openclaw", "Asistente personal local-first multi-canal (responde por WhatsApp/Telegram/…)", "Local-first; TS/Node",
         "No (modalidad mensajería)", "Otra modalidad: chat por mensajería, no voz + control del escritorio."],
    ],
)
p("Además, orientados a domótica/intents (sin LLM que decida ni computer-use): Rhasspy, "
  "Willow, Dicio, Neon AI. Y Jan, que es chat con LLM local pero sin manos-libres ni "
  "computer-use.", italic=True)

h("B. Agentes de computer-use y frameworks (adyacentes, no asistentes de voz locales)", 2)
table(
    ["Proyecto", "Qué es", "Local / Nube", "Posición frente a Gemma 4 Agent"],
    [
        ["Agent S3 (simular-ai)", "Computer-use de GUI (OSWorld 62.6% base; 72.6% supera el baseline humano en su anuncio)", "Híbrido: modelo grande de nube (GPT-5) + grounding UI-TARS auto-hospedable", "Muy potente, pero no corre en hardware modesto; Gemma 4 opera el SO local en 4 GB."],
        ["OS-Copilot / FRIDAY", "Agente de SO con self-learning (benchmark GAIA)", "Nube (requiere OpenAI key); desarrollo estancado desde 2024", "Depende de nube; no es un asistente de voz local."],
        ["Open Interpreter", "Ejecuta código en lenguaje natural", "Local (Ollama/LM Studio/Jan) o nube (GPT-4o)", "Herramienta de código, no un asistente de voz; sin verificación por estado del SO."],
        ["OpenHands (ex-OpenDevin)", "Agente de ingeniería de software (SWE-bench ~72-77%)", "Agnóstico: local / nube / enterprise (Docker opcional)", "Foco en código/dev, no asistente personal por voz."],
        ["Goose (Block)", "Agente extensible (desktop/CLI) + MCP, en Rust", "Local (Ollama) o nube; sin voz nativa", "Dev-céntrico y sin voz; con LLM chico el tool-calling falla (mismo límite que un 4B)."],
        ["Mark-XXXIX", "Asistente de voz tipo Jarvis (proyecto de un solo dev, ~770★)", "Nube de Google (Gemini Live API, free tier)", "Concepto cercano (voz), pero el cerebro vive en la nube de Google; Gemma 4 es 100% local."],
        ["AutoGen (Microsoft)", "Framework multi-agente (hoy en maintenance mode; sucesor: Microsoft Agent Framework)", "Framework, agnóstico (ejemplos en nube)", "Framework para desarrolladores, no un producto; asume modelos fuertes."],
        ["LangGraph (LangChain)", "Framework de orquestación por grafos (MIT)", "Framework, agnóstico (local o nube)", "Infraestructura de orquestación, no un asistente de usuario final."],
        ["AutoGPT", "Plataforma low-code de agentes (ya no el loop autónomo de 2023)", "Self-host (Ollama) o nube; licencia parcial NO-OSS (PolyForm Shield)", "Plataforma para construir agentes, no un asistente de voz; parte del código no es OSS puro."],
    ],
)
p("Veredicto honesto: hay un ecosistema activo de asistentes locales (la mayoría "
  "domótica/intents) y de clones tipo Jarvis con LLM local —el más cercano, isair/jarvis, "
  "también sobre Gemma, pide 8 GB+ de VRAM y solo controla Chrome—. El hueco que ocupa "
  "Gemma 4 Agent es la INTERSECCIÓN de los cuatro ejes de arriba. No competimos con GPT-4 "
  "en la nube; competimos por ser el mejor asistente que corre, completo, en la máquina "
  "del usuario.", bold=True)

# ====================== 5. RIESGOS Y MITIGACIONES ======================
h("6. Riesgos y mitigaciones", 1)
table(
    ["Riesgo", "Mitigación (de diseño)"],
    [
        ["VRAM de 4 GB insuficiente / OOM al cargar visión",
         "Modelo E2B-Q4 (3.36 GB con visión, medido); visión residente y GATEADA; KV cuantizable; watchdog de VRAM (nvidia-smi)."],
        ["Crash de CUDA en prompts largos (bug del kernel flash-attn + SWA)",
         "flash-attn OFF por defecto (estable 37/37 medido); system prompt \"lean\" para no cruzar el umbral."],
        ["GPU saturada por un juego → la app se cae o se vuelve lenta",
         "La interfaz renderiza por CPU (no compite por la GPU); fallback automático: el LLM pasa a CPU y le DEVUELVE la VRAM al juego. Nunca se mata el juego."],
        ["Usuario sin GPU NVIDIA (gráfica integrada / sin gráfica)",
         "La arquitectura ya es CPU-capable (LLM en CPU + STT/TTS en CPU). Pendiente en roadmap: binario CPU/Vulkan + auto-selección del perfil CPU."],
        ["Tool-calling débil del modelo chico (~75%)",
         "El router ofrece solo un SUBSET de herramientas; reintento forzado; recuperación por tipo de error; tool-picking guiado por memoria."],
        ["El LLM alucina o \"miente\" sobre lo que hizo",
         "Verificación ESTRUCTURAL por estado del SO (tristate honesto: sí/no/no-sé), nunca un juez-LLM. \"No miente\" es un invariante del producto."],
        ["Acciones irreversibles o que tocan recursos del usuario",
         "Política de confirmación; manejo seguro de contraseñas; el agente NUNCA cierra procesos ajenos (juegos, editores) sin confirmación explícita."],
        ["Privacidad de los datos del usuario",
         "100% local: sin nube, sin telemetría, sin cuentas. \"local · no telemetry\"."],
        ["Latencia de voz alta (UX mala)",
         "Prefix-cache (~1 s menos por acción), prompts lean, STT Parakeet rápido (~74 ms), streaming de TTS por oraciones."],
        ["RAM ajustada en laptops de 8 GB (modo CPU)",
         "El modelo se mapea con mmap (páginas evictables bajo presión); roadmap: descarga del server en idle + límite de hilos."],
        ["Inestabilidad del motor (llama-server caído / zombie)",
         "Auto-recuperación: se detecta el server muerto, se reinicia el gestionado y se reintenta el turno."],
        ["Dependencia de un solo proveedor de modelo",
         "Todo OSS y local (Gemma 4 + llama.cpp); el modelo es intercambiable, sin lock-in de nube."],
    ],
)

# ====================== CIERRE ======================
h("7. Resumen ejecutivo", 1)
p("Gemma 4 Agent NO es \"el único asistente local por voz\" —existen varios, e incluso un "
  "clon tipo Jarvis que también usa Gemma—. Compite por una INTERSECCIÓN que ningún "
  "proyecto revisado reúne a la vez: un asistente de IA por voz 100% local, privado, "
  "gratis, multilingüe y honesto, que además opera el escritorio de forma GENÉRICA (UIA/"
  "OCR/visión, no solo Chrome ni solo domótica), verifica cada acción por ESTADO del SO "
  "(\"no miente\") y entra en hardware modesto (4 GB de VRAM, o incluso sin gráfica, en "
  "CPU). Su arquitectura está diseñada alrededor de las restricciones reales del hardware "
  "del usuario y de un principio innegociable: el modelo decide y el sistema verifica — no "
  "inventa.")

# ====================== 8. FUENTES ======================
h("8. Fuentes (verificadas en esta investigación)", 1)
p("Asistentes locales / de voz: isair/jarvis (github.com/isair/jarvis) · dnhkng/GLaDOS "
  "(github.com/dnhkng/GLaDOS) · Home Assistant Assist (home-assistant.io/blog/2025/09/11/"
  "ai-in-home-assistant) · OpenVoiceOS (openvoiceos.org) · Leon AI (github.com/leon-ai/leon) "
  "· Rhasspy (rhasspy.readthedocs.io) · Willow (heywillow.io) · Jan (github.com/janhq/jan).")
p("Agentes de computer-use / frameworks: Agent S (github.com/simular-ai/Agent-S; arXiv "
  "2510.02250) · OS-Copilot (github.com/OS-Copilot/OS-Copilot) · Open Interpreter "
  "(github.com/OpenInterpreter/open-interpreter) · OpenHands (github.com/OpenHands/OpenHands) "
  "· Goose (github.com/block/goose) · Mark-XXXIX (github.com/FatihMakes/Mark-XXXIX) · "
  "openclaw (github.com/openclaw/openclaw) · AutoGen (github.com/microsoft/autogen) · "
  "LangGraph (github.com/langchain-ai/langgraph) · AutoGPT (github.com/Significant-Gravitas/AutoGPT).")
p("Datos del producto (rendimiento CPU, VRAM, latencia) medidos en este repo; ver scripts "
  "scripts/_measure_cpu_inference.py y la memoria del proyecto.", italic=True)


def _save(document, path):
    """Guarda en `path`; si está bloqueado (Word abierto), escribe una copia
    `_corregido` para no fallar ni pisar el archivo abierto."""
    try:
        document.save(str(path))
        return path
    except PermissionError:
        alt = path.with_name(path.stem + "_corregido.docx")
        document.save(str(alt))
        return alt


saved = _save(doc, OUT)
print(f"[ok] informe generado: {saved}")
