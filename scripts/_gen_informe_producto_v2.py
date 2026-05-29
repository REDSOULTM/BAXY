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
  "y se combinan con cualquier motor de hardware (CPU o GPU). Es un diferenciador central: "
  "ningún competidor local-de-voz ofrece garantías de accesibilidad de este tipo.", italic=True)

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

# ====================== 4. COMPETIDORES ======================
h("5. Panorama competitivo", 1)
p("Análisis de 10 proyectos del espacio de agentes. La conclusión clave: ninguno "
  "ocupa el mismo nicho — todos son nube, modelos grandes, o frameworks de "
  "orquestación. El único asistente de voz personal comparable (Mark-XXXIX) depende "
  "de una API de nube paga.")
table(
    ["Competidor", "Qué es", "Recursos", "Posición frente a Gemma 4 Agent"],
    [
        ["Agent-S", "Computer-use / GUI (OSWorld 72%)", "GPT-4V / UI-TARS, nube", "No corre local; nosotros operamos el SO en 4 GB."],
        ["OS-Copilot", "Automatización del SO + self-learning", "GPT, nube, sesgo monolingüe", "Nube + atado a un idioma; le tomamos la idea de error-recovery."],
        ["Open Interpreter", "Ejecuta código en lenguaje natural", "Claude/LiteLLM (soporta local)", "Inspira la tool de código (en nuestro caso, gateada y segura)."],
        ["OpenHands", "Agente de software enterprise", "Anthropic/OpenAI, nube/Docker", "Enterprise y nube; no es un asistente de voz personal."],
        ["Goose", "Agente local en Rust + MCP", "50+ providers, llama-cpp-2", "Local pero dev-céntrico y sin voz; su MCP es nuestro gap estratégico."],
        ["Mark-XXXIX", "Asistente de voz tipo Jarvis (el más parecido)", "Gemini 2.5 LiveAPI, nube PAGA", "El más cercano, pero NUBE PAGA; nosotros somos local y gratis."],
        ["openclaw", "Gateway multi-canal (WhatsApp, etc.)", "TS, infra de producción", "Otro producto (mensajería), no un asistente personal local."],
        ["AutoGen", "Multi-agente conversacional", "N modelos grandes", "No entra en 4 GB."],
        ["LangGraph", "Máquina de estados / DAG de agentes", "Framework", "Framework de orquestación, no un producto."],
        ["AutoGPT", "Loop autónomo + memoria episódica", "Framework", "Le tomamos la memoria episódica de errores."],
    ],
)
p("Veredicto: en nuestro terreno (local · 4 GB · voz · privado · gratis · multilingüe · "
  "honesto) no hay rival directo. El objetivo no es superar a GPT-4 en la nube, sino ser "
  "el mejor asistente que corre en la máquina del usuario.", bold=True)

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
p("Gemma 4 Agent compite en un nicho propio: el único asistente de IA por voz que es "
  "100% local, privado, gratis, multilingüe y honesto, y que corre en hardware modesto. "
  "Su arquitectura está diseñada alrededor de las restricciones reales del hardware del "
  "usuario (4 GB de VRAM, o incluso sin gráfica) y de un principio innegociable: el "
  "modelo decide y el sistema verifica — no inventa.")

doc.save(str(OUT))
print(f"[ok] informe generado: {OUT}")
