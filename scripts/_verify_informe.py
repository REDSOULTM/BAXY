"""Verifica el .docx generado: que los claims DAÑINOS estén ausentes y las
correcciones presentes. Falla ruidoso si algo está mal."""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from docx import Document

ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT / "Gemma4_Agent_Producto_Riesgos_y_Competencia_v2.docx"
if not DOCX.exists():
    alt = ROOT / "Gemma4_Agent_Producto_Riesgos_y_Competencia_v2_corregido.docx"
    DOCX = alt if alt.exists() else DOCX

doc = Document(str(DOCX))
parts = [p.text for p in doc.paragraphs]
for t in doc.tables:
    for row in t.rows:
        for c in row.cells:
            parts.append(c.text)
text = "\n".join(parts)
low = text.lower()

# DAÑINOS — deben estar AUSENTES
bad = ["le tomamos", "le tomamos la idea", "le tomamos la memoria",
       "inspira la tool", "nos tomamos", "tomamos de", "sesgo monolingüe",
       "no hay rival directo", "nube paga"]
# CORRECCIONES — deben estar PRESENTES
good = ["isair/jarvis", "maintenance mode", "polyform", "free tier",
        "20 tok", "uia → ocr", "no es \"el único", "intersección",
        "62.6%", "openvoiceos", "glados"]

print(f"[doc] {DOCX.name} — {len(parts)} bloques de texto")
print("=" * 70)
fails = 0
for b in bad:
    hit = b.lower() in low
    print(f"  [{'FALLA' if hit else 'ok  '}] AUSENTE? {b!r}: {'PRESENTE (mal)' if hit else 'ausente'}")
    if hit:
        fails += 1
print("-" * 70)
for g in good:
    hit = g.lower() in low
    print(f"  [{'ok  ' if hit else 'FALLA'}] PRESENTE? {g!r}: {'si' if hit else 'FALTA (mal)'}")
    if not hit:
        fails += 1
print("=" * 70)
print(f"[VEREDICTO] {'OK — informe corregido' if fails == 0 else f'REVISAR ({fails} problemas)'}")
sys.exit(1 if fails else 0)
