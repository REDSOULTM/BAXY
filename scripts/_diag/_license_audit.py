"""Auditoría de licencias para VENDER el producto. Lista todas las deps instaladas
(importlib.metadata, sin instalar nada) + su licencia, y FLAGGEA las problemáticas
(GPL/AGPL/non-commercial = veneno comercial; LGPL = nota). Escribe un reporte markdown."""
from __future__ import annotations
import sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import importlib.metadata as im

# Patrones de licencia
BAD = ("agpl", "affero")                 # AGPL = el peor para comercial
GPL = ("gpl-3", "gpl-2", "gplv3", "gplv2", "gpl ", "gnu general public", "gpl)")
LGPL = ("lgpl", "lesser general public")  # OK si se usa por dynamic-linking sin modificar
NC = ("non-commercial", "noncommercial", "cc-by-nc", "cc by-nc", "research only",
      "research-only", "non commercial", "prosperity", "proprietary", "no commercial")
PERMISSIVE = ("mit", "bsd", "apache", "isc", "python software", "psf", "zlib", "cc0",
              "unlicense", "public domain", "mpl-2", "mozilla", "boost", "0bsd", "wtfpl")

def _lic_of(meta) -> str:
    parts = []
    lic = (meta.get("License") or "").strip()
    if lic and len(lic) < 120 and "\n" not in lic:
        parts.append(lic)
    for c in (meta.get_all("Classifier") or []):
        if c.startswith("License"):
            parts.append(c.replace("License :: ", "").replace("OSI Approved :: ", ""))
    return " | ".join(dict.fromkeys(p for p in parts if p)) or "(sin metadata)"

rows = []
for d in im.distributions():
    try:
        meta = d.metadata
        name = meta["Name"]; ver = meta["Version"]
    except Exception:
        continue
    lic = _lic_of(meta)
    low = lic.lower()
    if any(x in low for x in BAD):
        cat = "AGPL"
    elif any(x in low for x in LGPL):       # LGPL ANTES que GPL ('lgpl' contiene 'gpl')
        cat = "LGPL"
    elif "exception" in low and any(x in low for x in GPL):
        cat = "GPL-EXCEPTION"               # GPLv2-with-FOSS/bootloader-exception = OK comercial
    elif any(x in low for x in GPL):
        cat = "GPL"
    elif any(x in low for x in NC):
        cat = "NON-COMMERCIAL"
    elif any(x in low for x in PERMISSIVE):
        cat = "OK"
    else:
        cat = "REVISAR"
    rows.append((name, ver, lic, cat))

rows.sort(key=lambda r: (r[3] != "AGPL", r[3] != "GPL", r[3] != "NON-COMMERCIAL",
                         r[3] != "LGPL", r[3] != "REVISAR", r[0].lower()))
order = {"AGPL": 0, "GPL": 1, "NON-COMMERCIAL": 2, "LGPL": 3, "REVISAR": 4, "OK": 5}
from collections import Counter
counts = Counter(r[3] for r in rows)

out = Path("documentacion/AUDITORIA_licencias.md")
lines = ["# Auditoría de licencias — viabilidad COMERCIAL", "",
         f"Total: **{len(rows)} paquetes**. Generado por scripts/_diag/_license_audit.py.", "",
         "## Resumen", ""]
for cat in ("AGPL", "GPL", "NON-COMMERCIAL", "LGPL", "GPL-EXCEPTION", "REVISAR", "OK"):
    n = counts.get(cat, 0)
    mark = {"AGPL": "🚫", "GPL": "🚫", "NON-COMMERCIAL": "🚫", "LGPL": "⚠️",
            "GPL-EXCEPTION": "✅", "REVISAR": "❓", "OK": "✅"}[cat]
    lines.append(f"- {mark} **{cat}**: {n}")
lines += ["", "## 🚫 BLOQUEANTES para vender (AGPL/GPL/non-commercial)", ""]
blockers = [r for r in rows if r[3] in ("AGPL", "GPL", "NON-COMMERCIAL")]
if blockers:
    for n, v, l, c in blockers:
        lines.append(f"- **{n}** {v} — `{c}` — {l}")
else:
    lines.append("**Ninguno.** ✅ No hay deps AGPL/GPL/non-commercial instaladas.")
lines += ["", "## ⚠️ LGPL (OK por dynamic-linking, no modificar la lib)", ""]
lgpls = [r for r in rows if r[3] == "LGPL"]
lines += [f"- {n} {v} — {l}" for n, v, l, c in lgpls] or ["(ninguno)"]
lines += ["", "## ❓ REVISAR a mano (metadata ambigua)", ""]
rev = [r for r in rows if r[3] == "REVISAR"]
lines += [f"- {n} {v} — {l}" for n, v, l, c in rev] or ["(ninguno)"]
lines += ["", "## MODELOS (NO los cubre pip — chequear a mano)", "",
          "- **Gemma 4** (`models/`): Apache 2.0 (desde 2026) ✅",
          "- **mmproj** (visión, parte de Gemma): Apache 2.0 ✅",
          "- **Whisper** (STT): MIT ✅ — pero chequear el checkpoint exacto usado",
          "- **Piper VITS** (TTS): MIT el motor; **cada VOZ tiene su licencia** (algunas CC-BY / no-comercial) — CHEQUEAR la voz que se distribuya",
          "- **Wake-word (LiveKit)**: Apache 2.0 ✅",
          "- **Encoder router (sentence-transformers FT)**: Apache 2.0 (base) ✅", ""]
out.write_text("\n".join(lines), encoding="utf-8")

print(f"[audit] {len(rows)} paquetes. Bloqueantes={len(blockers)} LGPL={len(lgpls)} REVISAR={len(rev)}")
print("[bloqueantes AGPL/GPL/non-commercial]:")
for n, v, l, c in blockers:
    print(f"  🚫 {n} {v}: {c} — {l[:50]}")
if not blockers:
    print("  ✅ NINGUNO")
print("[REVISAR a mano]:", ", ".join(n for n, v, l, c in rev) or "ninguno")
print(f"[reporte] documentacion/AUDITORIA_licencias.md")
