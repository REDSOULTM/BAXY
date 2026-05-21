"""Post-fine-tune pipeline: rebuild artifacts with the new encoder + evaluate.

After scripts/train_router_encoder.py produces the fine-tuned encoder, the rest
of the router stack must be re-derived with THAT encoder (its vector geometry
changed): the Tool2Vec centroids re-embedded, the abstain head retrained on the
new feature distribution, then the holdout measured ONCE.

This wires GEMMA4_SEMANTIC_MODEL to the fine-tuned dir for the whole sequence so
every component sees the same encoder, exactly as the runtime would with that
env set. Reproducible: one command regenerates everything from the FT model.

Run (CPU is fine):
    python scripts/router_ft_pipeline.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FT_DIR = ROOT / "gemma4_agent" / "data" / "router_encoder_ft"
PY = sys.executable


def _run(cmd: list[str], env: dict) -> None:
    print(f"\n$ {' '.join(cmd)}")
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        raise SystemExit(f"step failed: {cmd}")


def main() -> int:
    if not FT_DIR.exists():
        print(f"missing {FT_DIR} — run train_router_encoder.py first")
        return 1
    env = dict(os.environ)
    env["GEMMA4_SEMANTIC_MODEL"] = str(FT_DIR)
    print(f"using fine-tuned encoder: {FT_DIR}")

    # 1. Re-embed Tool2Vec centroids with the FT encoder.
    _run([PY, "scripts/router_tool2vec_build.py"], env)
    # 2. Retrain the abstain head on the FT feature distribution.
    _run([PY, "scripts/train_abstain_head.py", "--recall-floor", "0.95"], env)
    # set threshold 0.68 (dev-tuned balanced point)
    import json
    p = ROOT / "gemma4_agent" / "data" / "abstain_head.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["threshold"] = 0.68
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print("abstain head threshold -> 0.68")
    # 3. Evaluate both splits with the FT encoder active.
    _run([PY, "scripts/router_eval.py", "--split", "both"], env)
    print("\nDONE. To make the FT encoder the runtime default, set "
          "GEMMA4_SEMANTIC_MODEL to the ft dir (or wire it in config).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
