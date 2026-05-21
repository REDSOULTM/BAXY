"""Step 6 (CONDITIONAL): fine-tune the router encoder on our own distribution.

The four research reports agreed that the base multilingual encoder is the
ceiling for SHORT voice queries (MTEB rank does not transfer to tool retrieval;
ToolRet arXiv:2503.01763). The fix is a student trained on OUR distribution:
synthetic multilingual (query -> correct tool) pairs, contrastive loss with
in-batch + hard negatives, so the embedding space is shaped for tool intent
instead of generic topical similarity.

This is the "12-hour overnight lower-risk variant" from the research (no
cross-encoder teacher needed at v1 — the Tool2Vec synthetic pairs already give
supervised positives; in-batch negatives + mined hard negatives do the rest).

INPUTS (reproducible, versioned):
  - gemma4_agent/data/tool2vec_queries.jsonl   (synthetic query->tool pairs)
  - gemma4_agent/data/router_eval_corpus.curated.jsonl  (DEV split only; the
    holdout hashes are EXCLUDED so the student never sees them)
OUTPUT:
  - a fine-tuned sentence-transformer dir, then ONNX-int8 exported for runtime.

ANTI-OVERFIT: training uses ONLY dev-split real rows + synthetic queries (which
are model-generated, never holdout text). A universality slice (PT/IT held out
from synthetic generation) validates that the gain is not Spanish-only.

Run in the CUDA venv (4060 Ti):
  .venv_router_train\\Scripts\\python.exe scripts/train_router_encoder.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERIES = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"
CORPUS = ROOT / "gemma4_agent" / "data" / "router_eval_corpus.curated.jsonl"
TOOL_DESC_OUT = ROOT / "gemma4_agent" / "data" / "router_encoder_meta.json"
OUT_DIR = ROOT / "gemma4_agent" / "data" / "router_encoder_ft"
_HOLDOUT_SALT = "router-eval-2026-05-20"
_BASE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _split_of(q: str) -> str:
    h = hashlib.sha256((_HOLDOUT_SALT + q).encode("utf-8")).hexdigest()
    return "holdout" if (int(h[:8], 16) % 5 == 0) else "dev"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--base", default=_BASE)
    ap.add_argument("--no-onnx", action="store_true")
    ap.add_argument("--smoke", action="store_true",
                    help="tiny run (1 epoch, 400 pairs) to validate the pipeline")
    ap.add_argument("--limit", type=int, default=0, help="cap training pairs")
    args = ap.parse_args()
    if args.smoke:
        args.epochs = 1
        args.limit = 400

    import torch
    from sentence_transformers import (
        SentenceTransformer, InputExample, losses, models,
    )
    from torch.utils.data import DataLoader

    print(f"CUDA: {torch.cuda.is_available()}  device: "
          f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}")

    from gemma4_agent.semantic_router import TOOL_DESCRIPTIONS

    # Positives: synthetic (query, tool-description) pairs + dev real rows.
    pairs: list[tuple[str, str]] = []
    for ln in QUERIES.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        d = json.loads(ln)
        desc = TOOL_DESCRIPTIONS.get(d["tool"])
        if desc:
            pairs.append((d["q"], desc))
    # Real dev rows: query -> each expected tool's description (holdout excluded).
    for ln in CORPUS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if _split_of(r["q"]) != "dev":
            continue
        for t in (r.get("expected") or []):
            desc = TOOL_DESCRIPTIONS.get(t)
            if desc:
                pairs.append((r["q"], desc))
    print(f"training pairs: {len(pairs)} (synthetic + dev real; holdout excluded)")
    if args.limit:
        import random
        random.Random(7).shuffle(pairs)
        pairs = pairs[: args.limit]
        print(f"  limited to {len(pairs)} pairs")

    examples = [InputExample(texts=[q, d]) for q, d in pairs]
    loader = DataLoader(examples, shuffle=True, batch_size=args.batch)

    model = SentenceTransformer(args.base, device="cuda" if torch.cuda.is_available() else "cpu")
    # MultipleNegativesRankingLoss = in-batch negatives contrastive — the
    # standard recipe for (query, positive) pairs; every other positive in the
    # batch is a negative. Pulls a query toward its tool and away from others.
    loss = losses.MultipleNegativesRankingLoss(model)

    warmup = int(len(loader) * args.epochs * 0.1)
    model.fit(
        train_objectives=[(loader, loss)],
        epochs=args.epochs,
        warmup_steps=warmup,
        show_progress_bar=True,
        output_path=str(OUT_DIR),
    )
    print(f"fine-tuned model -> {OUT_DIR}")

    # Reproducibility guard (2026-05-21): newer transformers write a tokenizer
    #_config referencing a `TokenizersBackend` class that older transformers
    # can't load, which silently DISABLES the router on a version mismatch. The
    # fine-tune does not change the vocab, so we overwrite the saved tokenizer
    # with the BASE model's portable tokenizer files. This makes the artifact
    # load across transformers versions.
    try:
        import shutil
        from huggingface_hub import snapshot_download
        base = snapshot_download(args.base)
        for f in ("tokenizer_config.json", "tokenizer.json",
                  "sentencepiece.bpe.model", "special_tokens_map.json",
                  "unigram.json", "vocab.txt"):
            src = Path(base) / f
            if src.exists():
                shutil.copy(src, OUT_DIR / f)
        print("  pinned base tokenizer into the FT dir (cross-version safe)")
    except Exception as exc:
        print(f"  WARN: could not pin base tokenizer ({exc}); the model may "
              "fail to load on a different transformers version.")

    TOOL_DESC_OUT.write_text(json.dumps({
        "base": args.base, "epochs": args.epochs, "batch": args.batch,
        "n_pairs": len(pairs),
        "note": "student trained on synthetic Tool2Vec queries + dev real rows; "
                "holdout excluded by stable hash.",
    }, indent=2), encoding="utf-8")

    if not args.no_onnx:
        try:
            _export_onnx_int8(OUT_DIR)
        except Exception as exc:
            print(f"ONNX export skipped ({exc}); the ST dir still works on CPU.")
    return 0


def _export_onnx_int8(model_dir: Path) -> None:
    """Export the fine-tuned encoder to ONNX int8 for fast CPU runtime."""
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    from optimum.onnxruntime import ORTQuantizer

    onnx_dir = model_dir.parent / "router_encoder_onnx"
    m = ORTModelForFeatureExtraction.from_pretrained(str(model_dir), export=True)
    m.save_pretrained(str(onnx_dir))
    q = ORTQuantizer.from_pretrained(str(onnx_dir))
    qconfig = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)
    q.quantize(save_dir=str(onnx_dir), quantization_config=qconfig)
    print(f"ONNX int8 -> {onnx_dir}")


if __name__ == "__main__":
    sys.exit(main())
