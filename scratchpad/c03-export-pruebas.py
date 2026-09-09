"""Export existing C03 paired transcripts verbatim; never rerun a product test."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/comprobaciones/C03"
REPORT = BASE / "PRUEBAS_C03_PARA_EMMAN.md"


def link(path, label):
    return f"[{label}](<{path.as_posix()}>)"


def literal(value):
    value = str(value)
    fence = "`" * max(3, max((len(x) + 1 for x in re.findall(r"`+", value)), default=3))
    return f"{fence}text\n{value}\n{fence}\n"


raw = subprocess.run(
    ["git", "ls-files", "-co", "--exclude-standard", "-z", "--", "artifacts/comprobaciones/C03"],
    cwd=ROOT, capture_output=True, check=True,
).stdout
paths = sorted({ROOT / value.decode("utf-8") for value in raw.split(b"\0")
                if value and value.decode("utf-8").endswith("/paired.json")})
priority = [
    "astra-lora-pilot2-product",
    "astra-qwen2507-corpus-warm", "astra-qwen2507-corpus-inherited", "astra-qwen2507-mute-state",
    "astra-qwen2507-completed-request", "astra-qwen2507-quoted-title",
    "astra-qwen2507-window-title-literal-resume",
    "astra-qwen2507-window-title-contract", "astra-qwen2507-window-title-target",
    "astra-qwen2507-window-title", "astra-qwen2507-cancel-outcome", "astra-baseline",
]
paths.sort(key=lambda p: (priority.index(p.parent.name) if p.parent.name in priority else len(priority), p.parent.name))
captures = []
for path in paths:
    if path.stat().st_size > 20_000_000:
        raise RuntimeError(f"Inspect unexpectedly large source before exporting: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(data, list) and all(isinstance(r, dict) for r in data), path
    captures.append((path, data))
total = sum(len(rows) for _, rows in captures)
published = sum(row.get("terminal") == "published_final" for _, rows in captures for row in rows)
stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
lines = [
    "# Pruebas de C03: lo que pedí y lo que BAXY respondió\n",
    f"Exportado: {stamp}. Rama de trabajo: Goal-c03. **C03 sigue EN_CURSO.**\n",
    f"Este archivo reúne **{total} turnos de {len(captures)} capturas emparejadas** que ya existen en C03. "
    f"{published} tienen un terminal de respuesta publicada. **Eso no significa {published} respuestas correctas.** "
    "Incluye intentos fallidos, peticiones repetidas, averías inyectadas y capturas anteriores a esta sesión. "
    "No son los 100 turnos nuevos de aceptación, que siguen pendientes.\n",
    "## Cómo leerlo\n",
    f"Empieza por {link(BASE/'PRUEBAS_RECIENTES_C03.md', 'las 21 respuestas integradas más recientes y sus fallos')}. "
    "Ese informe corto también recoge cuatro reproducciones y las pruebas automáticas actuales.\n",
    "- **Entrada literal**: el texto que se envió al producto como mensaje del usuario.\n"
    "- **Respuesta literal**: el final registrado, sin corregir gramática, inventos ni idioma.\n"
    "- **Estado técnico**: lo que registró el conductor; `published_final` sólo significa que publicó.\n"
    "- **Adjudicación**: enlace a la evaluación existente, cuando la hay. No he inventado aprobaciones para las capturas sin adjudicación.\n"
    "- **Auditoría de composición**: incluye borradores y rechazos internos cuando se registraron; no todos fueron visibles.\n",
    "La entrada literal no es el prompt interno completo del modelo. Las instrucciones internas y los hechos "
    "están en las auditorías enlazadas cuando fueron capturados. No hay un registro completo de todos los prompts "
    "internos históricos. Los ensayos directos de GGUF sin `paired.json` no están mezclados con estos turnos del producto.\n",
    f"Las últimas 18 respuestas directas sobre contexto están en {link(BASE/'PRUEBAS_CONTEXTO_C03.md', 'el anexo de diagnóstico')}, "
    "con peticiones, respuestas literales y evaluación individual. No se suman a los turnos del producto ni a su aceptación.\n",
    f"La comparación de modelos heredados tiene otras 36 respuestas en {link(BASE/'PRUEBAS_GEMMA_C03.md', 'el anexo Gemma')}, "
    "también separadas y adjudicadas individualmente. Ninguno de esos candidatos ha sido promovido.\n",
    f"El primer ajuste tiene 42 respuestas comparadas en {link(BASE/'PRUEBAS_AJUSTE_C03.md', 'el anexo de ajuste')}. "
    "Muestra mejoras parciales y fallos restantes; tampoco acredita cierre.\n",
    "## Qué está fallando ahora\n",
    f"La {link(BASE/'ACLARACION_DUENO_2026-09-06.md', 'aclaración del dueño')} corrige la rúbrica: español es válido ante entradas mixtas y una explicación simple no tiene que ser exhaustiva. Las evaluaciones anteriores basadas únicamente en alternancia o exhaustividad quedan pendientes de recalibrar.\n",
    f"Diagnóstico posterior: {link(BASE/'PRUEBAS_AJUSTE_3_C03.md', '78 respuestas del tercer ajuste')}. "
    "Mejora formato (4/12 a 9/12) pero introduce una explicación falsa del hielo y otra contradictoria del cifrado. "
    "No está promovido ni acredita mejora integrada. "
    f"La {link(BASE/'PRUEBAS_ESCALA_C03.md', 'prueba de intensidad del adaptador')} empeoró y quedó descartada.\n",
    "La captura más reciente, lora-pilot2-product, publicó 21 respuestas: 17 aprobadas y 4 no aprobadas tras la aclaración del dueño "
    "según revisión manual. Persisten fallos de precisión, spanglish y formato. La hora contradictoria "
    "de t5 se detecta tras corregir el verificador; el reintento aún repite la respuesta. "
    "El cierre confirmado de la ventana propia sí quedó verificado. El adaptador no está promovido.\n",
    f"Su comparación directa separada tiene 54 respuestas en {link(BASE/'PRUEBAS_AJUSTE_2_C03.md', 'el segundo ajuste')}; "
    "ninguna se suma a la aceptación. Los párrafos siguientes describen capturas anteriores, no el estado final.\n",
    "El cierre por título ya funciona en la captura quoted-title: se identifica la ventana de prueba, "
    "se cancela sin cerrarla y se cierra después de una nueva confirmación. Sus seis respuestas llegaron, "
    "pero la cancelación y el resumen todavía usan prosa técnica innecesaria. Antes, window-title-contract "
    'sólo obtuvo 2/6 respuestas útiles y fieles: proponía `process="null"` y pedía un proceso pese a recibir el título. '
    "Las capturas recientes aparecen primero y sus adjudicaciones distinguen publicación, fidelidad y naturalidad. "
    "Siguen pendientes calidad conceptual, spanglish y consistencia de las rutas; no hay panel de aceptación aprobado.\n",
    "La captura completed-request publicó sus 21 respuestas. Su turno 6 dice «el audio está desactivado» "
    "aunque los hechos dicen muted=false; el turno 15 ignora la petición explícita de Spanglish. "
    "El resumen del cierre ya conserva el objetivo original y omite la resolución/maximización interna, "
    "pero todavía añade una coletilla técnica. Cada turno tiene evaluación en su ADJUDICACION.md.\n",
    "La representación alternativa muteState no corrigió esa inversión y fue retirada. Después se heredaron "
    "el corpus semántico calibrado y su caché exacta desde el BAXY anterior; el servicio ahora carga 25.156 registros "
    "con política compatible. Eso restablece una dependencia y no acredita calidad de respuesta. Las capturas "
    "corpus-inherited y corpus-warm distinguen el arranque frío de la preparación previa a enviar mensajes.\n",
    "La captura cancel-outcome de 21 turnos, colocada después, enseña preguntas de conocimiento, español, inglés, "
    "spanglish, lecturas reales, confirmación, cancelación y cierre de una ventana de prueba. Incluyo también "
    "la referencia inicial astra-baseline (10/16 útiles según su adjudicación). Son conjuntos diferentes: "
    "no se deben convertir en una supuesta mejora porcentual del producto entero.\n",
    "## Pruebas automáticas recientes\n",
    "Estas pruebas usan contratos, fixtures y, en algunos casos, respuestas simuladas. Complementan las "
    "conversaciones reales de abajo; no certifican por sí solas la calidad del modelo.\n",
    "| Comprobación | Resultado recogido | Evidencia |\n|---|---|---|",
    f"| Conservación de petición y contrato de composición tras corregir horas escritas | 125 pass | {link(ROOT/'scratchpad/c03-word-clock-owner-final.log', 'log')} |",
    f"| `test_source_quality.ps1 -Mode Fast` tras corregir horas escritas | Verde; build sin errores ni advertencias | {link(ROOT/'scratchpad/c03-word-clock-fast.log', 'log')} |",
    f"| Proveedor de ventanas: Win32, títulos, procesos compartidos e identidad | 14 pass | {link(ROOT/'scratchpad/c03-window-title-explicit-provider.log', 'log')} |",
    f"| Integración: transporte de título y selector, hechos | 23 pass | {link(ROOT/'scratchpad/c03-window-title-explicit-integration.log', 'log')} |",
    f"| `pytest tests/test_planner.py tests/test_turn_policy.py tests/test_effect_intent.py tests/test_c03_request_preservation.py -q` | 2586 pass, 104 subtests | {link(ROOT/'scratchpad/c03-window-title-contract-recheck.log', 'log')} |",
    f"| `pytest tests/test_planner.py -q`, tras último cambio del normalizador | 146 pass, 104 subtests | {link(ROOT/'scratchpad/c03-window-title-optional-tests.log', 'log')} |",
    f"| Resumen: objetivo original y hechos, C03FactPreservation / Goal06VisibleVoice / MindPlanSession (.NET) | 42 pass | {link(BASE/'ASTRA-TRAMO-19.md', 'tramo 19')} |",
    f"| Contrato Python de composición tras conservar completedRequest | 109 pass | {link(ROOT/'scratchpad/c03-completed-request-python.log', 'log')} |",
    f"| Composición, conservación de petición y voz tras retirar muteState | 120 pass | {link(ROOT/'scratchpad/c03-mute-state-restored.log', 'log')} |",
    f"| Servicio real de evidencia tras herencia exacta | 25.156 registros, política compatible | {link(BASE/'RESTAURACION_ENCODER.md', 'restauración')} |",
    "| Ruff de los seis archivos Python de esta tanda | Pass | Salida de la sesión y checkpoint |",
    "| Full final, UI real y 100 nuevos | **Pendientes** | No se declaran aprobados |\n",
    "También se conservan los fallos intermedios: 2344 pass/2 fail (fixtures de despedida pedían inglés "
    "con idioma configurado en español); 2585 pass/1 fail (test exigía una frase antigua del prompt). "
    "Se corrigieron esas expectativas manteniendo los contratos de idioma y las opciones de confirmación.\n",
    "## Contexto y reanudación\n",
    f"El estado operativo está en {link(BASE/'CHECKPOINT.md', 'CHECKPOINT.md')}, "
    f"y las decisiones recientes en {link(BASE/'ASTRA-TRAMO-24.md', 'ASTRA-TRAMO-24.md')}. "
    "Los archivos permanecen aunque se compacte la conversación. Este informe es una instantánea; "
    "no crea otra tarea ni ejecuta pruebas nuevas.\n",
    "## Índice de capturas\n",
]
for index, (path, rows) in enumerate(captures, 1):
    count = sum(r.get("terminal") == "published_final" for r in rows)
    lines.append(f"- [Captura {index:03d}: {path.parent.name}](#captura-{index:03d}) — {len(rows)} turnos, {count} publicados.")

manifest = {"generatedAt": stamp, "captureCount": len(captures), "turnCount": total, "publishedTerminals": published, "sources": []}
checks = []
for index, (path, rows) in enumerate(captures, 1):
    folder = path.parent
    lines.extend([f'\n<a id="captura-{index:03d}"></a>\n', f"## Captura {index:03d}: {folder.name}\n"])
    lines.append("Origen: " + ("campaña Astra" if folder.name.startswith("astra-") else "evidencia anterior conservada") + ".\n")
    refs = [link(path, "transcripción JSON")]
    for name, label in [
        ("ADJUDICACION.md", "adjudicación"), ("PREREG.json", "prerregistro"),
        ("RESULT.json", "recursos y resultado"), ("events.jsonl", "eventos del producto"),
        ("compose-audit.jsonl", "composición y borradores"), ("argument-batches.jsonl", "prompts y salidas de argumentos"),
        ("resource-readiness.jsonl", "carga de recursos"), ("COMMAND_RELEASE.json", "preparación antes de enviar mensajes"),
    ]:
        target = folder/name
        if target.is_file():
            refs.append(link(target, label))
    lines.append(" · ".join(refs) + "\n")
    source = {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "turns": []}
    for n, row in enumerate(rows, 1):
        request = str(row.get("request") or "")
        answer = str(row.get("final") or "")
        lines.extend([f"### {n:03d} · {row.get('turnId', '')}\n", "**Entrada literal**\n", literal(request), "**Respuesta literal**\n"])
        lines.append(literal(answer) if answer else "**No hay respuesta final registrada.**\n")
        lines.append(f"Estado técnico: `{row.get('terminal') or 'sin terminal registrado'}`.\n")
        for key, label in [("compositionFailure", "Fallo de composición"), ("diagnostic", "Diagnóstico"), ("mindReplyRejection", "Rechazo registrado")]:
            if row.get(key):
                value = row[key] if isinstance(row[key], str) else json.dumps(row[key], ensure_ascii=False)
                lines.extend([f"{label}:\n", literal(value)])
        checks.extend([literal(request)] + ([literal(answer)] if answer else []))
        source["turns"].append({"turnId": row.get("turnId"), "requestSha256": hashlib.sha256(request.encode()).hexdigest(), "answerSha256": hashlib.sha256(answer.encode()).hexdigest(), "terminal": row.get("terminal")})
    manifest["sources"].append(source)
body = "\n".join(lines) + "\n"
assert all(value in body for value in checks)
assert lines.count("**Entrada literal**\n") == total
assert lines.count("**Respuesta literal**\n") == total
REPORT.write_text(body, encoding="utf-8")
assert REPORT.read_text(encoding="utf-8") == body
manifest["reportSha256"] = hashlib.sha256(REPORT.read_bytes()).hexdigest()
REPORT.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"report": str(REPORT), "captures": len(captures), "turns": total, "published": published, "bytes": REPORT.stat().st_size, "verbatimChecked": True}, ensure_ascii=False))
