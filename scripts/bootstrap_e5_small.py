"""Idempotent bootstrap for the e5-small ONNX router model (Sprint 8a).

Downloads `Xenova/multilingual-e5-small` int8 ONNX + tokenizer files
into ``~/.gemma4/models/e5-small/`` if they aren't already there.

Usage:
    python scripts/bootstrap_e5_small.py
    python scripts/bootstrap_e5_small.py --force      # re-download even if present

Idempotent: a second run on a complete tree exits in <1s without
re-downloading.

The downloaded files (~113MB for the quantized ONNX + ~5MB tokenizer)
are the inputs for ``gemma4_agent.router_v2``. If this script hasn't
run, ``router_v2.is_enabled()`` reports False and the agent silently
falls back to the existing planner/semantic_router stack.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


TARGET = Path.home() / ".gemma4" / "models" / "e5-small"
REQUIRED_FILES = (
    "onnx/model_quantized.onnx",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "config.json",
)


def _missing(target: Path) -> list[str]:
    return [p for p in REQUIRED_FILES if not (target / p).exists()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bootstrap_e5_small")
    parser.add_argument("--force", action="store_true",
                        help="re-download even if the model is already present")
    parser.add_argument("--target", type=Path, default=TARGET,
                        help=f"target directory (default: {TARGET})")
    args = parser.parse_args(argv)

    target: Path = args.target
    target.mkdir(parents=True, exist_ok=True)

    if not args.force:
        miss = _missing(target)
        if not miss:
            print(f"already complete at {target}")
            return 0
        print(f"missing files: {miss}")

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub not installed; pip install huggingface_hub",
              file=sys.stderr)
        return 2

    print(f"downloading Xenova/multilingual-e5-small → {target}")
    snapshot_download(
        repo_id="Xenova/multilingual-e5-small",
        local_dir=str(target),
        allow_patterns=["onnx/model_quantized.onnx", "tokenizer*", "*.json"],
    )

    miss_after = _missing(target)
    if miss_after:
        print(f"download finished but still missing: {miss_after}",
              file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
