"""Auditoría de flags de entorno GEMMA4_* — clasifica cada flag y detecta los REALMENTE
muertos. Reproducible, NO toca nada. Escribe documentacion/AUDITORIA_flags.md.

LECCIÓN (2026-06-01): un primer auditor ingenuo (solo `os.environ.get("LITERAL")`) marcó
64 flags como "muertos" — pero casi todos eran LIVE leídos por OTROS patrones:
  - IPC de subproceso: el padre hace env["GEMMA4_X"]=... y un PowerShell embebido lo lee
    con $env:GEMMA4_X (mover ventana, screenshot, notificación, UIA elevado).
  - subscript: os.environ["GEMMA4_X"].
  - helpers de config: _env_bool("GEMMA4_X", ...), _env_int(...), etc.
Borrarlos habría roto features. Por eso este auditor cuenta TODOS los patrones de lectura.

Clasificación:
  IPC      = se setea en env[...] de un subproceso Y/O se lee con $env: en un script.
  TOGGLE   = se lee con os.environ.get/getenv/_env_* (feature on/off o tuning).
  DEAD     = NO se lee por NINGÚN patrón (solo aparece en comentarios). Candidato a borrar.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2] / "gemma4_agent"
FLAG_RE = re.compile(r"GEMMA4_[A-Z0-9_]+")
# Lecturas Python: get/getenv/subscript + helpers _env_*.
PY_READ_RE = re.compile(
    r"(?:os\.environ\.get|os\.getenv|environ\.get|getenv|_env_bool|_env_int|"
    r"_env_str|_env_float|_env_flag|_env_list|_env)\(\s*[\"'](GEMMA4_[A-Z0-9_]+)[\"']")
SUBSCRIPT_RE = re.compile(r"environ(?:\.get)?\[\s*[\"'](GEMMA4_[A-Z0-9_]+)[\"']")
PS_READ_RE = re.compile(r"\$env:(GEMMA4_[A-Z0-9_]+)")          # PowerShell (IPC)
IPC_SET_RE = re.compile(r"env\[\s*[\"'](GEMMA4_[A-Z0-9_]+)[\"']\s*\]\s*=")


def _iter_prod():
    for p in ROOT.rglob("*.py"):
        s = str(p)
        if "test" in s or "_diag" in s or "__pycache__" in s:
            continue
        yield p


all_flags: set[str] = set()
py_read: set[str] = set()
ps_read: set[str] = set()
ipc_set: set[str] = set()
in_code: set[str] = set()      # aparece en ≥1 línea de CÓDIGO (no comentario)
loc: dict[str, str] = {}

for p in _iter_prod():
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    rel = p.relative_to(ROOT.parent)
    for i, line in enumerate(text.splitlines(), 1):
        is_comment = line.lstrip().startswith("#")
        for m in FLAG_RE.finditer(line):
            all_flags.add(m.group(0))
            loc.setdefault(m.group(0), f"{rel}:{i}")
            if not is_comment:
                in_code.add(m.group(0))
        for m in PY_READ_RE.finditer(line):
            py_read.add(m.group(1))
        for m in SUBSCRIPT_RE.finditer(line):
            py_read.add(m.group(1))
        for m in PS_READ_RE.finditer(line):
            ps_read.add(m.group(1))
        for m in IPC_SET_RE.finditer(line):
            ipc_set.add(m.group(1))

# DEAD ROBUSTO: el flag aparece SOLO en comentarios (nunca como literal en código).
# Cualquier mención en código (get/helper/_env_off/constante ENV_FLAG=.../dict UI/$env:)
# implica que se usa — los reads indirectos (constante, multilínea, helper) son
# indetectables por regex directa, así que "está en código" es el criterio seguro.
toggle = sorted(f for f in all_flags if f in py_read)
ipc_only = sorted(f for f in (ps_read | ipc_set) if f not in py_read)
dead = sorted(f for f in all_flags if f not in in_code)

out = [
    "# Auditoría de flags GEMMA4_* (scripts/_diag/_flag_audit.py)",
    "",
    f"Total: **{len(all_flags)}**  |  leídos como TOGGLE/config: **{len(toggle)}**  |  "
    f"solo IPC de subproceso ($env:/env[...]): **{len(ipc_only)}**  |  "
    f"DEAD (sin lectura): **{len(dead)}**",
    "",
    "## 🗑️ DEAD — sin NINGUNA lectura (toggle, subscript, $env: ni env[...]=). Borrables.",
    "",
]
out += ([f"- **{f}** — {loc.get(f,'?')}" for f in dead]
        or ["**Ninguno.** Todos los flags se leen por algún patrón. ✅"])
out += ["", "## 🔌 SOLO-IPC — env de subproceso (NO borrar: rompe el worker PowerShell)", ""]
out += [f"- {f} — {loc.get(f,'?')}" for f in ipc_only] or ["(ninguno)"]
out += ["", f"## ✅ TOGGLE/config ({len(toggle)}) — feature on/off o tuning", ""]
out += [f"- {f}" for f in toggle]

(ROOT.parent / "documentacion" / "AUDITORIA_flags.md").write_text("\n".join(out), encoding="utf-8")
print(f"[flags] total={len(all_flags)} toggle={len(toggle)} ipc_only={len(ipc_only)} DEAD={len(dead)}")
print("[DEAD]:", ", ".join(dead) if dead else "NINGUNO")
print("[reporte] documentacion/AUDITORIA_flags.md")
