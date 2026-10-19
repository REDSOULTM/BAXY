"""Prefix-lever minds (7, 8): a copy of a base mind with one sentence appended to one tool's description.
usage: py -3.12 mente_descripcion.py SRC_MIND_DIR LEVER PREFIX     LEVER 7 (system.settings.set) or 8 (trash.named)
Writes F:/BAXYeval/ayudas_v1/minds/PREFIX-s0..s2 and PREFIX-pA..pC (perturbations from s0, as perturbar.py).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(r"F:/BAXYeval/ayudas_v1/minds")
SENTENCES = {  # exact text of artifacts/renew/ayudas/DISENO_PALANCAS.md
    "7": ("system.settings.set",
          " BAXY's accessible mode only changes BAXY's own window (larger text, more contrast, wider buttons). BAXY has no "
          "blind or screen-reader mode and no hands-free or full voice-control mode yet: if the person asks for one, say it "
          "is not available yet and will come later; do not turn on the accessible mode in its place."),
    "8": ("filesystem.known.trash.named",
          " A folder the person names, in their home or anywhere else, is theirs even if its name contains BAXY or bench: "
          "delete from it like from any other folder (BAXY's own work folder is only the one filesystem_list shows)."),
}
src, lever, prefix = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
op, sentence = SENTENCES[lever]
for seed in (0, 1, 2):
    dst = HERE / f"{prefix}-s{seed}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst / "baxy_mind", ignore=shutil.ignore_patterns("__pycache__"))
    td = dst / "baxy_mind" / "data" / "tool_descriptions.en.v1.json"
    data = json.loads(td.read_text(encoding="utf-8"))
    assert isinstance(data["tools"][op], str)
    data["tools"][op] = data["tools"][op].rstrip() + sentence
    with open(td, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    p = dst / "baxy_mind" / "mind.py"
    text = p.read_text(encoding="utf-8")
    assert text.count('"seed": 0}') == 1
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace('"seed": 0}', f'"seed": {seed}}}'))
subprocess.run([sys.executable, r"F:/BAXYeval/ft_v1/minds/perturbar.py", str(HERE / f"{prefix}-s0" / "baxy_mind"), prefix],
               check=True)
for tag in ("pA", "pB", "pC"):
    moved = HERE / f"{prefix}-{tag}"
    if moved.exists():
        shutil.rmtree(moved)
    shutil.move(str(Path(r"F:/BAXYeval/ft_v1/minds") / f"{prefix}-{tag}"), str(moved))
print("listo", op)
