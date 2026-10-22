"""System One: a «model soup» of Laya checkpoints — the element-wise average of the weights of models fine-tuned from the
same start (Wortsman et al., ICML 2022, «Model soups: averaging weights of multiple fine-tuned models improves accuracy
without increasing inference time»).

usage: py -3.12 -X utf8 scripts/renew/system_one/soup.py OUTDIR RUN_DIR RUN_DIR [RUN_DIR ...]
Averages model.safetensors of the runs (same shapes), copies the first run's encoder/ and tokenizer/ and its config with
the runs' calibration temperatures averaged, so llama.cpp's converter reads OUTDIR as one more Laya checkpoint.
"""
import json
import shutil
import sys
from pathlib import Path

import torch
from safetensors.torch import load_file, save_file


def main():
    out, runs = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    if len(runs) < 2:
        raise SystemExit("a soup needs at least two runs")
    states = [load_file(str(run / "model.safetensors")) for run in runs]
    soup = {}
    for name, first in states[0].items():
        if first.is_floating_point():
            soup[name] = (sum(s[name].float() for s in states) / len(states)).to(first.dtype)
        else:
            soup[name] = first
    out.mkdir(parents=True, exist_ok=True)
    save_file(soup, str(out / "model.safetensors"), metadata={"format": "pt"})
    for sub in ("encoder", "tokenizer"):
        shutil.copytree(runs[0] / sub, out / sub, dirs_exist_ok=True)
    configs = [json.loads((run / "rl_agent_config.json").read_text(encoding="utf-8")) for run in runs]
    config = configs[0]
    temps = [c.get("temperature") for c in configs]
    if all(isinstance(t, list) and len(t) == len(temps[0]) for t in temps):
        config["temperature"] = [sum(v) / len(v) for v in zip(*temps)]
    (out / "rl_agent_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print("soup of", len(runs), "runs ->", out, "temperature", config.get("temperature"))


if __name__ == "__main__":
    torch.set_grad_enabled(False)
    main()
