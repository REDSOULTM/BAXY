"""Parte A de la verificación B4/B6 (calidad, SIN LLM): ¿los tools data_analysis
(CSV) y document (PDF) FUNCIONAN sobre archivos reales? Responde "¿lo hace bien?"
a nivel de capacidad. La Parte B (¿el 4B los elige en vivo?) va aparte."""
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.domain_tools.data_analysis import data_analysis_tool
from gemma4_agent.domain_tools.document import document_tool
from gemma4_agent.memory_pkg.state import AgentState


def _make_pdf(path: Path, text: str) -> None:
    """PDF 1.4 mínimo con texto extraíble (offsets calculados — pypdf lo lee)."""
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
state = AgentState(path=tmp / "state.json")

csv = tmp / "ventas.csv"
csv.write_text("producto,mes,unidades,ingreso\nlaptop,enero,12,18000\n"
               "mouse,enero,80,1600\nlaptop,febrero,15,22500\nmouse,febrero,95,1900\n",
               encoding="utf-8")

print("=== B4: data_analysis sobre CSV real ===")
prof = data_analysis_tool({"action": "csv_profile", "path": str(csv)}, state)
print(f"  csv_profile : ok={prof.get('ok')} rows={prof.get('rows')} cols={prof.get('columns') or prof.get('column_count')}")
q = data_analysis_tool({"action": "csv_query", "path": str(csv), "query": "unidades > 50"}, state)
qrows = q.get("count") or len(q.get("rows") or q.get("result") or [])
print(f"  csv_query   : ok={q.get('ok')} 'unidades>50' -> {qrows} filas (esperado 2: mouse x2)")
b4_ok = bool(prof.get("ok")) and bool(q.get("ok"))

pdf = tmp / "reporte.pdf"
_make_pdf(pdf, "Reporte Gemma4: las ventas subieron 23 por ciento este trimestre.")
print("\n=== B6: document sobre PDF real ===")
ext = document_tool({"action": "extract_text", "path": str(pdf)}, state, knowledge_executor=None)
txt = (ext.get("text") or ext.get("text_preview") or "")
print(f"  extract_text: ok={ext.get('ok')} chars={len(txt)}")
print(f"  contenido   : {txt[:90]!r}")
b6_ok = bool(ext.get("ok")) and ("ventas" in txt.lower() or "gemma4" in txt.lower())

print("\n=== VEREDICTO Parte A (capacidad) ===")
print(f"  B4 data_analysis CSV: {'OK' if b4_ok else 'FAIL'}")
print(f"  B6 document PDF     : {'OK' if b6_ok else 'FAIL'}")
