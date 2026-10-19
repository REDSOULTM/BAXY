"""Lever 9 minds: a copy of a base mind whose turn-opening message (the clock, a message of its own before the person's
words, so nothing of the examples is read as theirs) ends with 1-3 similar requests that went well and their calls,
from F:/BAXYeval/ayudas_v1/palanca9/recuperados.json (recuperar_p9.py).
usage: py -3.12 mente_palanca9.py SRC_MIND_DIR PREFIX
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(r"F:/BAXYeval/ayudas_v1/minds")
src, prefix = Path(sys.argv[1]), sys.argv[2]
OLD = '        self.conversation.append({"role": "user", "content": self._clock() + self._pending_note(pending)})\n'
NEW = '        self.conversation.append({"role": "user", "content": self._clock() + self._pending_note(pending) + _examples(text)})\n'
HELPER = '''

_RETRIEVED: dict | None = None


def _examples(text: str) -> str:
    """Lever 9 (ayudas): 1-3 similar requests that went well, with their calls, retrieved by embeddings (offline here)."""
    global _RETRIEVED
    if _RETRIEVED is None:
        _RETRIEVED = json.loads(Path(r"F:/BAXYeval/ayudas_v1/palanca9/recuperados.json").read_text(encoding="utf-8"))
    chosen = _RETRIEVED.get(text) or []
    return ("\\n[Pedidos parecidos que salieron bien: " + "; ".join(chosen) + "]") if chosen else ""


class Mind:'''
for seed in (0, 1, 2):
    dst = HERE / f"{prefix}-s{seed}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst / "baxy_mind", ignore=shutil.ignore_patterns("__pycache__"))
    p = dst / "baxy_mind" / "mind.py"
    t = p.read_text(encoding="utf-8")
    assert t.count(OLD) == 1 and t.count("\n\nclass Mind:") == 1 and t.count('"seed": 0}') == 1
    t = t.replace(OLD, NEW).replace("\n\nclass Mind:", HELPER, 1).replace('"seed": 0}', f'"seed": {seed}}}')
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
subprocess.run([sys.executable, r"F:/BAXYeval/ft_v1/minds/perturbar.py", str(HERE / f"{prefix}-s0" / "baxy_mind"), prefix],
               check=True)
for tag in ("pA", "pB", "pC"):
    moved = HERE / f"{prefix}-{tag}"
    if moved.exists():
        shutil.rmtree(moved)
    shutil.move(str(Path(r"F:/BAXYeval/ft_v1/minds") / f"{prefix}-{tag}"), str(moved))
print("listo")
