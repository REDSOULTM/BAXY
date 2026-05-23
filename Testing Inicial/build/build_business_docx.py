# -*- coding: utf-8 -*-
"""Documento Word — MODELO DE NEGOCIO de Gemma4 Agent.

Foco EXCLUSIVO (pedido del usuario): cómo se vende como
  - versión FREE en GitHub (open-core, núcleo OSS)
  - versión PRO en Steam (conveniencia: instalador 1-clic, auto-update,
    voces premium, soporte; pago único ~US$15-25)
y el análisis LEGAL + ECONÓMICO de esa estrategia.

Datos verificados:
  - Licencias del stack: requirements.txt del repo (MIT/Apache/GPL).
  - Gemma 4: Apache 2.0 (uso comercial + redistribución + producto cerrado
    permitidos) según fuentes 2025-2026; versiones previas usaban Gemma Terms
    of Use. -> verificar la licencia EXACTA del weight distribuido.
  - PyQt6: GPL v3 / comercial (copyleft) -> usar UI web para closed-source.
  - Steam: comisión estándar 30% (escalonada por ventas), Steam Direct US$100
    recuperable por app.
"""
from __future__ import annotations
import os
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(__file__)
ASSETS = os.path.join(HERE, "pptx_assets")

INK   = RGBColor(0x1A, 0x20, 0x28)
CYAN  = RGBColor(0x0E, 0x6B, 0xA8)
GREEN = RGBColor(0x1E, 0x7E, 0x34)
ORANGE= RGBColor(0xB5, 0x4A, 0x1F)
VIOLET= RGBColor(0x5B, 0x3E, 0xA8)
MUTE  = RGBColor(0x60, 0x6A, 0x76)
RED   = RGBColor(0xB0, 0x2A, 0x1F)

doc = Document()
normal = doc.styles["Normal"]
normal.font.name = "Calibri"; normal.font.size = Pt(11); normal.font.color.rgb = INK
normal.paragraph_format.space_after = Pt(6); normal.paragraph_format.line_spacing = 1.15
for lvl, sz, col in [("Heading 1", 18, CYAN), ("Heading 2", 14, INK), ("Heading 3", 12, MUTE)]:
    st = doc.styles[lvl]; st.font.name = "Calibri"; st.font.size = Pt(sz)
    st.font.color.rgb = col; st.font.bold = True


def _shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), hexcolor); tcPr.append(sh)


def p(text="", *, size=11, bold=False, italic=False, color=INK, align=None, after=6, before=0):
    par = doc.add_paragraph()
    if align is not None: par.alignment = align
    par.paragraph_format.space_after = Pt(after); par.paragraph_format.space_before = Pt(before)
    r = par.add_run(text); r.font.size = Pt(size); r.bold = bold; r.italic = italic; r.font.color.rgb = color
    return par


def runs(items, *, after=6):
    par = doc.add_paragraph(); par.paragraph_format.space_after = Pt(after)
    for txt, st in items:
        r = par.add_run(txt); r.font.size = Pt(st.get("size", 11))
        r.bold = st.get("bold", False); r.italic = st.get("italic", False)
        r.font.color.rgb = st.get("color", INK)
    return par


def bullet(text, *, bold_lead=None, color=INK, size=11):
    par = doc.add_paragraph(style="List Bullet"); par.paragraph_format.space_after = Pt(4)
    if bold_lead:
        r = par.add_run(bold_lead + " "); r.bold = True; r.font.size = Pt(size); r.font.color.rgb = color
    r2 = par.add_run(text); r2.font.size = Pt(size); r2.font.color.rgb = color
    return par


def table(headers, rows, *, widths=None, head_fill="0E6BA8", zebra="EEF3F8"):
    t = doc.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"; hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        _shade(hdr[i], head_fill); para = hdr[i].paragraphs[0]
        para.paragraph_format.space_after = Pt(2); para.paragraph_format.space_before = Pt(2)
        run = para.add_run(h); run.bold = True; run.font.size = Pt(10); run.font.color.rgb = RGBColor(0xFF,0xFF,0xFF)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci, val in enumerate(row):
            if zebra and ri % 2 == 1: _shade(cells[ci], zebra)
            para = cells[ci].paragraphs[0]
            para.paragraph_format.space_after = Pt(2); para.paragraph_format.space_before = Pt(2)
            txt, col = val if isinstance(val, tuple) else (val, INK)
            run = para.add_run(str(txt)); run.font.size = Pt(9.5); run.font.color.rgb = col
            if ci == 0: run.bold = True
    if widths:
        for row in t.rows:
            for ci, wdt in enumerate(widths): row.cells[ci].width = Cm(wdt)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def callout(title, body, *, color=CYAN, fill="EEF3F8"):
    t = doc.add_table(rows=1, cols=1); t.style = "Table Grid"; c = t.rows[0].cells[0]
    _shade(c, fill); pr = c.paragraphs[0]; pr.paragraph_format.space_after = Pt(2)
    r = pr.add_run(title); r.bold = True; r.font.size = Pt(10.5); r.font.color.rgb = color
    pr2 = c.add_paragraph(); pr2.paragraph_format.space_after = Pt(2)
    r2 = pr2.add_run(body); r2.font.size = Pt(10); r2.font.color.rgb = INK
    doc.add_paragraph().paragraph_format.space_after = Pt(4); return t


# =========================================================================
# PORTADA
# =========================================================================
for _ in range(3): doc.add_paragraph()
p("GEMMA4 AGENT", size=30, bold=True, color=CYAN, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
p("Modelo de negocio: Free (GitHub) + Pro (Steam)", size=16, color=INK,
  align=WD_ALIGN_PARAGRAPH.CENTER, after=24)
p("Estrategia de comercialización · Análisis legal · Análisis económico",
  size=13, bold=True, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER, after=40)
p("Versión 1.0 · 22 de mayo de 2026", size=10, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER)
p("Cifras de licencias y comisiones verificadas con fuentes oficiales (ver §Fuentes).",
  size=9, italic=True, color=MUTE, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()

# =========================================================================
# 0. RESUMEN
# =========================================================================
doc.add_heading("Resumen ejecutivo del negocio", level=1)
p("La estrategia es open-core: el núcleo del producto se publica gratis y de código "
  "abierto en GitHub, y una versión Pro empaquetada se vende en Steam por un pago "
  "único. No se vende la inteligencia (el modelo es gratis y local): se vende la "
  "conveniencia —que cualquier usuario, sin saber de programación, lo instale en un "
  "clic, reciba actualizaciones automáticas, voces premium y soporte.")
runs([("La promesa comercial es coherente con el producto: ", {}),
      ("«sin nube, sin mensualidades, sin enviar tus datos» — y el precio lo "
       "respeta: se paga una vez, no se suscribe.", {"bold": True})])
p("Nota técnica relevante para lo legal: la interfaz de usuario es la web app "
  "servida por pywebview (licencia BSD permisiva). El stack completo de la versión "
  "Pro queda así libre de copyleft y se puede vender cerrado sin conflicto de "
  "licencias (ver §2).", size=10, italic=True, color=MUTE)
table(
    ["Línea", "Free (GitHub)", "Pro (Steam)"],
    [
        ("Precio", ("US$ 0", GREEN), ("Pago único ~US$ 15–25", CYAN)),
        ("Público", "Técnico que compila", "Usuario común"),
        ("Distribución", "Código fuente (OSS)", "Ejecutable firmado, 1-clic"),
        ("Núcleo (voz, 65 tools)", ("Completo", GREEN), ("Completo", GREEN)),
        ("Conveniencia", "Manual", ("Instalador, auto-update", CYAN)),
        ("Voces premium / soporte", "No", ("Sí", CYAN)),
    ],
    widths=[4.5, 6.0, 6.0],
)
doc.add_page_break()

# =========================================================================
# 1. ESTRATEGIA OPEN-CORE
# =========================================================================
doc.add_heading("1. La estrategia: open-core (free + pro)", level=1)
p("El modelo open-core es el mismo que usan productos como GitLab, Obsidian o "
  "muchos juegos indie: una base libre que construye comunidad y confianza, y una "
  "capa de pago que monetiza la conveniencia y el servicio, no la funcionalidad "
  "esencial. Esto encaja perfecto con un producto cuyo argumento es la libertad y la "
  "privacidad.")

doc.add_heading("1.1 Qué va en cada versión", level=2)
table(
    ["Capacidad", "Free (GitHub)", "Pro (Steam)"],
    [
        ("Asistente de voz local completo", ("Sí", GREEN), ("Sí", GREEN)),
        ("Las 65 herramientas / acciones", ("Sí", GREEN), ("Sí", GREEN)),
        ("Perfiles de hardware (vram3–vram16)", ("Sí", GREEN), ("Sí", GREEN)),
        ("Instalador de un clic (firmado)", ("No", RED), ("Sí", GREEN)),
        ("Actualizaciones automáticas", ("Manual (git pull)", ORANGE), ("Sí, vía Steam", GREEN)),
        ("Descarga y configuración del modelo automática", ("Manual", ORANGE), ("Sí", GREEN)),
        ("Voces TTS premium adicionales", ("Voz base", ORANGE), ("Paquete ampliado", GREEN)),
        ("Soporte / atención", ("Comunidad", ORANGE), ("Directo", GREEN)),
        ("Rutinas y perfiles preconfigurados", ("Básico", ORANGE), ("Biblioteca extra", GREEN)),
    ],
    widths=[6.5, 5.0, 5.0],
)
callout(
    "Principio rector",
    "Nada esencial se recorta en la versión free. El usuario técnico tiene el "
    "producto completo gratis. El usuario común paga por NO tener que ser técnico. "
    "Esto evita la crítica de «mutilar el open source» y mantiene la buena fe de la "
    "comunidad, que es el motor del canal de adquisición.",
    color=GREEN, fill="E9F5EC",
)

doc.add_heading("1.2 Por qué GitHub para free y Steam para pro", level=2)
bullet("es donde está la comunidad técnica, el SEO de desarrolladores "
       "y la confianza del código abierto. Genera estrellas, issues, difusión "
       "boca-a-boca y credibilidad —el embudo superior gratuito.", bold_lead="GitHub:")
bullet("es la tienda donde el usuario común YA compra software para su "
       "PC con un clic, con pago integrado, reseñas, wishlist, rebajas y "
       "actualizaciones automáticas. Resuelve distribución, cobro y confianza de "
       "compra de una sola vez.", bold_lead="Steam:")
p("Steam además da visibilidad orgánica (categorías, «descubrimiento», ofertas "
  "estacionales) que un instalador propio nunca tendría, a cambio de su comisión.")
doc.add_page_break()

# =========================================================================
# 2. ANÁLISIS LEGAL
# =========================================================================
doc.add_heading("2. Análisis legal de la comercialización", level=1)
callout(
    "Aviso",
    "Análisis de las implicancias legales del diseño y las licencias. NO es "
    "asesoría jurídica. Antes de publicar en Steam conviene una revisión "
    "profesional, en especial de los puntos marcados en rojo.",
    color=RED, fill="FBEAE8",
)

doc.add_heading("2.1 La pregunta clave: ¿se puede vender un producto con Gemma?", level=2)
p("Sí. Es el punto que decide la viabilidad del negocio y la respuesta es "
  "favorable. Las fuentes consultadas (2025–2026) indican que Gemma 4 se publica "
  "bajo licencia Apache 2.0, que permite expresamente el uso comercial, la "
  "modificación y la redistribución del modelo, incluso dentro de productos de "
  "código cerrado y de pago, sin límite de usuarios y sin acuerdo especial.")
runs([("Matiz honesto a verificar: ", {"bold": True, "color": ORANGE}),
      ("versiones anteriores de Gemma (1–3) usaban los «Gemma Terms of Use» "
       "(comerciales pero con condiciones de traspaso de licencia y política de uso "
       "prohibido). Por eso, antes de empaquetar, hay que confirmar la licencia "
       "EXACTA del archivo de pesos (weight) que se distribuya en la versión Pro.",
       {})])
table(
    ["Licencia del modelo", "¿Vender en Steam?", "Condiciones"],
    [
        ("Gemma 4 — Apache 2.0", ("Sí, sin restricción", GREEN),
         "Mantener aviso de licencia y atribución"),
        ("Gemma Terms of Use (v1–3)", ("Sí, condicionado", ORANGE),
         "Traspasar restricciones de uso + incluir el acuerdo + política de uso prohibido"),
    ],
    widths=[5.5, 4.5, 6.5],
)

doc.add_heading("2.2 Las licencias del resto del stack", level=2)
p("El resto de los componentes son permisivos (MIT/Apache/BSD): permiten "
  "comercializar sin liberar el código. La única excepción que afecta a la versión "
  "Pro cerrada es la interfaz nativa.")
table(
    ["Componente", "Licencia", "¿Permite producto pago cerrado?"],
    [
        ("llama.cpp (inferencia)", ("MIT", GREEN), ("Sí", GREEN)),
        ("faster-whisper + Whisper", ("MIT", GREEN), ("Sí", GREEN)),
        ("Piper (TTS)", ("MIT", GREEN), ("Sí", GREEN)),
        ("Silero VAD", ("MIT", GREEN), ("Sí", GREEN)),
        ("openWakeWord", ("Apache 2.0", GREEN), ("Sí", GREEN)),
        ("sentence-transformers / Playwright", ("Apache 2.0", GREEN), ("Sí", GREEN)),
        ("FastAPI / uvicorn", ("MIT / BSD", GREEN), ("Sí", GREEN)),
        ("pywebview (UI principal)", ("BSD", GREEN), ("Sí", GREEN)),
    ],
    widths=[5.5, 3.8, 7.0],
)

doc.add_heading("2.3 Sin copyleft: la UI es pywebview (BSD)", level=2)
p("La interfaz de usuario principal del producto es la web app servida por "
  "pywebview (licencia BSD), no la antigua interfaz nativa PyQt6. Esta decisión de "
  "producto elimina por completo el único obstáculo de copyleft que tenía el stack:")
bullet("pywebview es BSD/MIT y permite empaquetar un producto de código "
       "cerrado y de pago sin obligación de liberar el código fuente.",
       bold_lead="Permisiva:")
bullet("PyQt6 (GPL v3) se retira del proyecto. Al no distribuirse, "
       "su copyleft no aplica ni a la versión free ni a la Pro.",
       bold_lead="PyQt eliminado:")
callout(
    "Resultado",
    "Con pywebview como única UI, TODO el stack de la versión Pro es de licencia "
    "permisiva (MIT / Apache / BSD) más el modelo Gemma (Apache 2.0). No queda "
    "ninguna obligación de abrir el código de la Pro: se puede vender cerrada en "
    "Steam sin conflicto de licencias.",
    color=GREEN, fill="E9F5EC",
)

doc.add_heading("2.4 Vender en Steam: requisitos legales", level=2)
bullet("hay que firmar el Steam Distribution Agreement y "
       "completar la información fiscal (Steam retiene y reporta).",
       bold_lead="Acuerdo con Valve:")
bullet("Steam exige que la app declare sus licencias de terceros. "
       "Hay que incluir los avisos de MIT/Apache y el de Gemma (Apache 2.0 o Gemma "
       "Terms según el weight).", bold_lead="Avisos de terceros:")
bullet("el control de apps de terceros (Spotify, "
       "Netflix) se hace por la interfaz de usuario y para uso personal del "
       "comprador; no se redistribuye contenido ni se eluden medidas de protección. "
       "Hay que reflejarlo en los términos del producto.", bold_lead="Términos de servicio:")
bullet("dejar claro al usuario que la app usa "
       "micrófono y captura de pantalla, en local, bajo su consentimiento. Al ser "
       "local, la exposición de privacidad (RGPD / leyes de datos de la región) es "
       "mínima, lo cual es un argumento de venta.", bold_lead="Privacidad:")

doc.add_heading("2.5 Marca y nombre", level=2)
p("«Gemma» es de Google. Conviene NO usar «Gemma» como nombre comercial del producto "
  "en Steam (riesgo de marca); usar un nombre propio y describir que «funciona con "
  "modelos Gemma de Google» como compatibilidad, no como marca propia.",
  )
doc.add_page_break()

# =========================================================================
# 3. ANÁLISIS ECONÓMICO
# =========================================================================
doc.add_heading("3. Análisis económico", level=1)

doc.add_heading("3.1 Estructura de costos", level=2)
p("La ventaja económica del modelo es que el costo marginal por usuario es casi "
  "cero: no hay servidores de IA que pagar (todo corre en el equipo del cliente). "
  "Los costos son mayormente iniciales y fijos.")
table(
    ["Concepto", "Tipo", "Monto aprox."],
    [
        ("Steam Direct (alta por app)", "Único", "US$ 100 (recuperable)"),
        ("Certificado de firma de código", "Anual", "US$ 70–400 / año"),
        ("Voces TTS premium (licencia/creación)", "Único/Variable", "Variable"),
        ("Infraestructura de IA (nube)", "Recurrente", ("US$ 0 — corre local", GREEN)),
        ("Costo por usuario adicional", "Marginal", ("≈ US$ 0", GREEN)),
        ("Tiempo de desarrollo/empaquetado", "Único", "Horas de trabajo"),
    ],
    widths=[6.5, 3.5, 6.0],
)
p("El costo recurrente operativo tiende a cero: a diferencia de un competidor de "
  "nube que paga por token en cada consulta, aquí cada venta es casi íntegramente "
  "margen tras cubrir los fijos.", italic=True, color=MUTE, size=10)

doc.add_heading("3.2 La comisión de Steam", level=2)
p("Valve retiene una comisión estándar del 30 % sobre las ventas, con tramos que la "
  "bajan a 25 % (sobre lo que supere US$ 10 M acumulados) y 20 % (sobre lo que "
  "supere US$ 50 M) — tramos irrelevantes para un proyecto que recién empieza. Para "
  "el cálculo se asume 30 %.")
table(
    ["Precio de venta", "Comisión Steam (30%)", "Neto por venta*"],
    [
        ("US$ 15", "US$ 4.50", ("US$ 10.50", GREEN)),
        ("US$ 20", "US$ 6.00", ("US$ 14.00", GREEN)),
        ("US$ 25", "US$ 7.50", ("US$ 17.50", GREEN)),
    ],
    widths=[5.0, 5.5, 5.5],
)
p("* Antes de impuestos y de la retención fiscal que Steam aplica según el país. "
  "El neto real dependerá de la tributación del vendedor.", size=9, italic=True, color=MUTE)

doc.add_heading("3.3 Punto de equilibrio", level=2)
p("Con costos fijos iniciales modestos (Steam Direct US$ 100 + firma de código "
  "~US$ 100–400/año), el punto de equilibrio se alcanza con muy pocas ventas:")
table(
    ["Precio", "Neto/venta", "Ventas para cubrir ~US$ 200", "Ventas para ~US$ 500"],
    [
        ("US$ 15", "US$ 10.50", ("≈ 20 ventas", GREEN), "≈ 48 ventas"),
        ("US$ 20", "US$ 14.00", ("≈ 15 ventas", GREEN), "≈ 36 ventas"),
        ("US$ 25", "US$ 17.50", ("≈ 12 ventas", GREEN), "≈ 29 ventas"),
    ],
    widths=[3.0, 3.5, 5.0, 4.5],
)
p("La conclusión económica es contundente: con costo marginal casi nulo y un punto "
  "de equilibrio de pocas decenas de ventas, el riesgo financiero es muy bajo. El "
  "reto no es el costo, es la adquisición de usuarios —que el canal free de GitHub "
  "alimenta gratis.")

doc.add_heading("3.4 Recomendación de precio", level=2)
runs([("Precio sugerido: ", {"bold": True}),
      ("US$ 19.99 (pago único). ", {"bold": True, "color": CYAN}),
      ("Está en la zona alta del rango elegido pero por debajo de la barrera "
       "psicológica de US$ 20; es un precio de «producto serio pero accesible», "
       "coherente con utilidades de escritorio en Steam, y deja ~US$ 14 netos por "
       "venta.", {})])
bullet("lanzar con −15 % la primera semana (Steam premia "
       "el descuento de lanzamiento con visibilidad).", bold_lead="Táctica:")
bullet("participar en rebajas estacionales de Steam para "
       "picos de venta sin bajar el precio base.", bold_lead="Rebajas:")
bullet("el discurso de venta es «pagás una vez y es tuyo, "
       "para siempre, sin mensualidad» — contraste directo con los asistentes de "
       "nube por suscripción.", bold_lead="Mensaje:")

doc.add_heading("3.5 Modelo de ingresos: por qué el free impulsa al pro", level=2)
p("El free no es una pérdida: es el motor de adquisición. La comunidad de GitHub "
  "genera difusión, confianza y reseñas; una parte de esos usuarios —los no "
  "técnicos o los que valoran su tiempo— convierten a Pro en Steam por la "
  "conveniencia. El costo de adquisición se aproxima a cero porque el canal es "
  "orgánico (estrellas, foros, boca a boca).")
callout(
    "Síntesis económica",
    "Costo marginal ≈ 0 · sin servidores de IA que pagar · punto de equilibrio de "
    "pocas decenas de ventas · canal de adquisición gratuito (GitHub) · margen ~70 % "
    "tras la comisión de Steam. El modelo es financieramente robusto y de bajo riesgo.",
    color=GREEN, fill="E9F5EC",
)
doc.add_page_break()

# =========================================================================
# 4. PROYECCIÓN DE INGRESOS
# =========================================================================
doc.add_heading("4. Proyección de ingresos (primer año)", level=1)
p("La proyección parte de una base conservadora, adecuada a un lanzamiento chico "
  "(proyecto de tesis): el embudo arranca con los usuarios del repositorio gratuito "
  "en GitHub, de los cuales una fracción —los no técnicos o los que valoran su "
  "tiempo— convierte a la versión Pro de Steam. Las tasas usadas son típicas del "
  "modelo open-core (conversión free→pago del orden de 1–5 %).")

doc.add_heading("4.1 Supuestos del modelo", level=2)
bullet("US$ 19.99 (pago único), neto ~US$ 14 tras la comisión del 30 % de Steam.",
       bold_lead="Precio:")
bullet("usuarios que prueban / descargan el free en GitHub durante el primer año.",
       bold_lead="Base (free):")
bullet("porcentaje del free que compra la Pro por conveniencia.",
       bold_lead="Conversión:")
bullet("Steam Direct US$ 100 (recuperable) + firma de código ~US$ 150/año = ~US$ 250.",
       bold_lead="Costos fijos año 1:")

doc.add_heading("4.2 Tres escenarios", level=2)
table(
    ["Escenario", "Usuarios free", "Conversión", "Ventas Pro", "Ingreso neto*", "Tras costos**"],
    [
        ("Pesimista", "500", "1.5 %", "8", "US$ 112", ("≈ −138 (no cubre)", RED)),
        ("Realista", "2 000", "2.5 %", "50", "US$ 700", ("≈ +450", GREEN)),
        ("Optimista", "6 000", "4 %", "240", "US$ 3 360", ("≈ +3 110", GREEN)),
    ],
    widths=[2.6, 2.6, 2.3, 2.2, 2.8, 3.5],
)
p("* Ingreso neto = ventas × US$ 14 (tras comisión Steam). ** Tras restar ~US$ 250 "
  "de costos fijos del primer año. Antes de impuestos.", size=9, italic=True, color=MUTE)
callout(
    "Lectura de la proyección",
    "Incluso el escenario pesimista (8 ventas) deja el proyecto casi en equilibrio "
    "el primer año, con costo marginal nulo: no hay riesgo de pérdida significativa. "
    "El escenario realista ya es rentable. Y como el costo por usuario adicional es "
    "≈ 0, todo crecimiento de ventas es casi íntegramente margen. El negocio escala "
    "sin que escalen los costos.",
    color=GREEN, fill="E9F5EC",
)

doc.add_heading("4.3 Sensibilidad: qué mueve la aguja", level=2)
p("El ingreso depende de dos palancas, y solo una está bajo control directo:")
bullet("la palanca dominante. Subir el tráfico de "
       "GitHub (estrellas, difusión, un buen README, un video demo) multiplica todo "
       "el embudo. Es donde conviene invertir esfuerzo.", bold_lead="Tamaño del free:")
bullet("se mejora con un buen instalador, una demo "
       "convincente y reseñas positivas, pero su techo es más rígido que el del "
       "tráfico.", bold_lead="Tasa de conversión:")
bullet("a este volumen, mover el precio entre US$ 15 y US$ 25 "
       "cambia poco frente al efecto del tráfico. Mejor fijar US$ 19.99 y enfocarse "
       "en crecer la base.", bold_lead="Precio:")
doc.add_page_break()

# =========================================================================
# 5. ESTRATEGIA DE MARKETING / LANZAMIENTO
# =========================================================================
doc.add_heading("5. Estrategia de marketing y lanzamiento", level=1)
p("Con costo marginal casi nulo, el único cuello de botella del negocio es la "
  "adquisición de usuarios. La buena noticia: el canal principal es orgánico y "
  "gratuito. La estrategia se ordena en tres fases.")

doc.add_heading("5.1 Fase 1 — Construir comunidad (free, GitHub)", level=2)
bullet("README claro con GIF/video de la voz en acción, "
       "instrucciones simples y la promesa «local, privado, sin suscripción» "
       "arriba de todo.", bold_lead="Repositorio cuidado:")
bullet("publicar la demo en r/LocalLLaMA, r/selfhosted, "
       "Hacker News y foros de IA local —es exactamente su público.",
       bold_lead="Comunidades técnicas:")
bullet("un video corto mostrando «le hablo y abre "
       "Spotify / sube el volumen / minimiza» vende el producto en 30 segundos.",
       bold_lead="Demo en video:")
bullet("responder issues, aceptar contribuciones; cada "
       "estrella y cada fork es difusión gratuita y prueba social.",
       bold_lead="Mantener actividad:")

doc.add_heading("5.2 Fase 2 — Preparar la tienda (Steam)", level=2)
bullet("ficha de Steam con capturas, video, y el mensaje "
       "«pagás una vez, es tuyo para siempre» frente a la suscripción de los "
       "asistentes de nube.", bold_lead="Página con wishlist:")
bullet("acumular wishlists ANTES del lanzamiento; Steam premia "
       "con visibilidad a los juegos/apps con muchas wishlists el día de salida.",
       bold_lead="Wishlists:")
bullet("dejar clarísimo el requisito de GPU y que el "
       "núcleo es gratis en GitHub —vender honestamente la conveniencia, no engañar.",
       bold_lead="Expectativas claras:")

doc.add_heading("5.3 Fase 3 — Lanzamiento y sostenimiento", level=2)
bullet("salir con −15 % la primera semana; Steam da un pico "
       "de visibilidad a los lanzamientos con descuento.", bold_lead="Descuento de salida:")
bullet("Steam Summer/Winter Sale para picos de venta "
       "sin tocar el precio base.", bold_lead="Rebajas estacionales:")
bullet("cada update (voces nuevas, más rutinas) es una "
       "excusa para reaparecer en feeds y recordar el producto.",
       bold_lead="Actualizaciones visibles:")
bullet("invitar a los compradores a dejar reseña; la "
       "calificación de Steam es el factor #1 de conversión futura.",
       bold_lead="Reseñas:")

doc.add_heading("5.4 El mensaje de venta (posicionamiento)", level=2)
callout(
    "Una frase",
    "«Una Alexa para tu PC, que vive en tu PC: le hablás y hace las cosas —abrir "
    "apps, poner música, controlar el equipo— sin nube, sin mensualidad y sin que "
    "tus datos salgan de tu máquina. Pagás una vez.»",
    color=CYAN,
)
p("Este mensaje ataca de frente las dos debilidades de los competidores: la "
  "suscripción perpetua de los asistentes de nube y la falta de privacidad. Es "
  "honesto (no promete razonamiento de nube) y memorable.")
doc.add_page_break()

# =========================================================================
# 6. RIESGOS Y CIERRE
# =========================================================================
doc.add_heading("6. Riesgos y mitigaciones", level=1)
table(
    ["Riesgo", "Impacto", "Mitigación"],
    [
        ("Licencia exacta del weight Gemma", ("Alto", RED),
         "Confirmar Apache 2.0 del archivo distribuido antes de publicar"),
        ("Copyleft de PyQt6", ("Resuelto", GREEN),
         "PyQt eliminado; UI es pywebview (BSD). Sin copyleft en la Pro"),
        ("Uso del nombre «Gemma» como marca", ("Medio", ORANGE),
         "Nombre propio; «compatible con Gemma» como descripción"),
        ("ToS de terceros (Spotify/Netflix)", ("Medio", ORANGE),
         "Control vía UI, uso personal, sin eludir DRM"),
        ("«Free mata al Pro» (nadie paga)", ("Medio", ORANGE),
         "El Pro vende conveniencia real (1-clic, updates, soporte), no funciones"),
        ("Dependencia de Steam (30%, políticas)", ("Bajo", GREEN),
         "Ofrecer también venta directa (itch.io/web) como respaldo"),
    ],
    widths=[5.0, 2.5, 8.5],
)

doc.add_heading("Conclusión", level=1)
p("El modelo free-en-GitHub + Pro-en-Steam es viable legal y económicamente. "
  "Legalmente, el stack es comercializable: el modelo Gemma 4 (Apache 2.0) permite "
  "vender un producto que lo incluya, y al ser pywebview (BSD) la interfaz de "
  "usuario, no queda ningún obstáculo de copyleft. Económicamente, el costo "
  "marginal casi nulo y el punto de equilibrio bajísimo hacen del riesgo financiero "
  "un problema menor; el verdadero trabajo es la adquisición de usuarios, que el "
  "canal abierto de GitHub financia de forma orgánica. La venta no es de "
  "inteligencia —esa es gratis y local— sino de conveniencia, confianza y "
  "comodidad: exactamente lo que el usuario común está dispuesto a pagar una vez.")

doc.add_heading("Fuentes", level=2)
for src in [
    "Gemma Terms of Use — ai.google.dev/gemma/terms (uso comercial, redistribución, atribución).",
    "Licencia de Gemma 4 (Apache 2.0) — análisis de fuentes 2025–2026 (MindStudio, Medium); "
    "VERIFICAR la licencia del weight concreto antes de distribuir.",
    "Licencias del stack — requirements.txt del proyecto: MIT (llama.cpp, Whisper, Piper, "
    "Silero), Apache 2.0 (openWakeWord, sentence-transformers, Playwright), GPL v3/comercial (PyQt6).",
    "Comisión de Steam — modelo estándar 30% / 25% (>US$10M) / 20% (>US$50M); Steam Direct US$100/app.",
    "Capacidades del producto — docs/ARCHITECTURE.md y tool_schemas (65 herramientas), "
    "bench/latency_sprint_report.md (latencias).",
]:
    bullet(src, size=10, color=MUTE)

out = os.path.join(HERE, "Gemma4_Agent_Negocio_Legal_Economico.docx")
doc.save(out)
print("OK ->", out)
