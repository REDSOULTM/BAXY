"""Prepare the original50 confirmation for the sealed deadline804 repair; no launch."""
from pathlib import Path
import ast
import hashlib
import json

root = Path(__file__).resolve().parents[1]
source = (root / "scratchpad/c03-process-batch803.py").read_text(encoding="utf-8")
for old, new in (
    ("PROCESS_BATCH803", "PROCESS_BATCH805"),
    ("C03-process-batch803-private", "C03-process-batch805-private"),
    ("C03-process-profile803", "C03-process-profile805"),
    ("process scope802", "process deadline804"),
    ("candidate802", "candidate804"),
    ("PROCESS_BUDGET802", "PROCESS_DEADLINE804"),
    ("PROCESS_VOCABULARY798", "PROCESS_DEADLINE804"),
    ("pins802", "pins804"),
    ("source802", "source804"),
    ("Complete Full798 exit0", "Complete Full804 exit0"),
    ("# Full798 covers the adopted combined baseline; Python-only802 requires its own gate.",
     "# Full804 covers cumulative Python802 plus C#804; own Fast is also required."),
):
    assert old in source, old
    source = source.replace(old, new)
source = source.replace("pins764 = read(ROOT / 'artifacts/comprobaciones/C03/DENSE_INVENTORY764/SOURCE_PINS.json')\n", "")
source = source.replace("{**pins804, **pins764}", "pins804")
source = source.replace("'source764_pins': pins764, ", "")
source = source.replace("           'source764_unchanged': all(sha(ROOT / path) == digest for path, digest in pins764.items()),\n", "")
assert "pins764" not in source
source = source.replace("assert sha(panel_path) == plan['panel_sha256']", """assert sha(panel_path) == plan['panel_sha256']
original = read(ROOT / 'artifacts/comprobaciones/C03/PROCESS_BATCH803/PREREG.json')
assert sha(panel_path) == original['panel_sha256']
assert sha(plan_path) == original['plan_sha256']""")
assert "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597" in source
assert source.count("3800") >= 2
ast.parse(source)
runner = root / "scratchpad/c03-process-batch805.py"
assert not runner.exists()
runner.write_bytes(source.encode("utf-8"))
review = (root / "scratchpad/c03-review-process803.py").read_text(encoding="utf-8")
review = review.replace("frozen803", "frozen805").replace("privadas803", "privadas805")
review = review.replace("C03-process-batch803-private", "C03-process-batch805-private").replace("PROCESS_BATCH803", "PROCESS_BATCH805")
review = review.replace("'source764_unchanged', 'source802_unchanged'", "'source804_unchanged'")
assert "source764_unchanged" not in review and "source802_unchanged" not in review
review = review.replace("import argparse", "import argparse\nimport hashlib")
review = review.replace("assert len(panel) == 50", """assert len(panel) == 50
prereg = read(public / 'PREREG.json')
assert hashlib.sha256((private / 'panel.json').read_bytes()).hexdigest() == prereg['panel_sha256']
assert [{'case_id': c['case_id'], 'group': c['group']} for c in panel] == prereg['cases']""")
ast.parse(review)
reviewer = root / "scratchpad/c03-review-process805.py"
assert not reviewer.exists()
reviewer.write_bytes(review.encode("utf-8"))
receipt = root / "artifacts/comprobaciones/C03/PROCESS_DEADLINE804/NEXT_CONFIRMATION.json"
assert not receipt.exists()
receipt.write_text(json.dumps({"panel": "Unchanged original50 from795; original803 panel and plan hashes required.",
    "required": "804 owners+Fast+Full exit0;28 pins intact;no concurrent tests/inference;4000MiB free RAM.",
    "runner": runner.as_posix(), "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
    "reviewer": reviewer.as_posix(), "reviewer_sha256": hashlib.sha256(reviewer.read_bytes()).hexdigest(),
    "adopted": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("805 prepared; model hash, original panel and resource limits retained. Not launched.")
