"""Parte B (CONEXIÓN REAL, en vivo): ¿el 4B ELIGE data_analysis (CSV) y document
(PDF) cuando se le pide analizar/leer esos archivos? O improvisa con otra tool
(filesystem/vision/office) = gap de routing. Varias variantes de fraseo (regla #3.5)."""
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ["GEMMA4_ACCESSIBILITY_MODE"] = "normal"
os.environ.pop("GEMMA4_STREAM_TTS", None)

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent


def _make_pdf(path: Path, text: str) -> None:
    stream = b"BT /F1 18 Tf 72 700 Td (" + text.encode("latin-1", "replace") + b") Tj ET"
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj" + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    path.write_bytes(out)


tmp = Path(tempfile.mkdtemp())
csv = tmp / "ventas.csv"
csv.write_text("producto,mes,unidades,ingreso\nlaptop,enero,12,18000\n"
               "mouse,enero,80,1600\nlaptop,febrero,15,22500\nmouse,febrero,95,1900\n",
               encoding="utf-8")
pdf = tmp / "reporte.pdf"
_make_pdf(pdf, "Reporte Gemma4: las ventas subieron 23 por ciento este trimestre.")

agent = Gemma4Agent()
agent.run_content("hola")

CASES = [
    ("CSV", f"analizá los datos del archivo {csv}", "data_analysis"),
    ("CSV", f"según el archivo {csv}, ¿cuántas unidades de mouse se vendieron en total?", "data_analysis"),
    ("CSV", f"hacé un resumen estadístico de {csv}", "data_analysis"),
    ("PDF", f"extraé el texto del archivo {pdf}", "document"),
    ("PDF", f"¿qué dice el archivo {pdf}?", "document"),
    ("PDF", f"resumime el contenido de {pdf}", "document"),
]
print("=" * 96)
hits = 0
for label, cmd, expected in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    r = agent.run_content(cmd)
    tools = [getattr(e, "name", "?") for e in (getattr(r, "tool_events", []) or [])]
    reply = (getattr(r, "content", "") or "")
    used = expected in tools
    if used:
        hits += 1
    short = cmd.replace(str(tmp), "…")
    print(f"[{'USA ' + expected if used else 'MISS (' + (tools[0] if tools else 'sin-tool') + ')'}] {label}: {short[:55]!r}")
    print(f"     tools={tools}")
    print(f"     reply={reply[:95]!r}")
    print("-" * 96)
print("=" * 96)
print(f"[VEREDICTO conexión real] el 4B eligió la tool específica en {hits}/{len(CASES)} casos")
