"""Lever 6 minds for screening: a copy of a base mind with this PC's home path added to the meaning of «folder».
usage: py -3.12 mente_palanca6.py SRC_MIND_DIR VARIANT PREFIX
  VARIANT a: only file.write's folder;  b: every file tool's folder (file.write/read/find/edit/open, trash.named)
Writes F:/BAXYeval/ayudas_v1/minds/PREFIX-s0..s2 (seeds) and PREFIX-pA..pC (perturbations, from s0 with perturbar.py).
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(r"F:/BAXYeval/ayudas_v1/minds")
src, variant, prefix = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
OPS = {"a": '{"file.write"}',
       "b": '{"file.write", "file.read", "file.find", "file.edit", "file.open", "filesystem.known.trash.named"}'}[variant]

OLD = """            for argument, meaning in (self.arguments.get(name) or {}).items():
                if isinstance(schema["properties"].get(argument), dict):
                    schema["properties"][argument]["description"] = meaning
"""
NEW = f"""            for argument, meaning in (self.arguments.get(name) or {{}}).items():
                if isinstance(schema["properties"].get(argument), dict):
                    # Lever 6 (ayudas): this PC's home, a fact of the machine, where the model fills the folder.
                    if argument == "folder" and name in {OPS}:
                        meaning += f" This PC's home folder is {{Path.home()}}."
                    schema["properties"][argument]["description"] = meaning
"""
HERE.mkdir(parents=True, exist_ok=True)
for seed in (0, 1, 2):
    dst = HERE / f"{prefix}-s{seed}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst / "baxy_mind", ignore=shutil.ignore_patterns("__pycache__"))
    p = dst / "baxy_mind" / "mind.py"
    text = p.read_text(encoding="utf-8")
    assert text.count(OLD) == 1
    text = text.replace(OLD, NEW)
    assert text.count('"seed": 0}') == 1
    text = text.replace('"seed": 0}', f'"seed": {seed}}}')
    if "from pathlib import Path" not in text:
        text = text.replace("import json\n", "import json\nfrom pathlib import Path\n", 1)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(dst, "ok")
# perturbar.py writes next to itself (ft_v1/minds); move the copies here.
subprocess.run([sys.executable, r"F:/BAXYeval/ft_v1/minds/perturbar.py", str(HERE / f"{prefix}-s0" / "baxy_mind"), prefix],
               check=True)
for tag in ("pA", "pB", "pC"):
    moved = HERE / f"{prefix}-{tag}"
    if moved.exists():
        shutil.rmtree(moved)
    shutil.move(str(Path(r"F:/BAXYeval/ft_v1/minds") / f"{prefix}-{tag}"), str(moved))
print("listo")
