"""QLoRA of Qwen3.5-4B on the decider's examples (D13). Loss only on the answer JSON; logits only there.

usage: train_decider.py --out DIR [--max N] [--epochs E] [--lr 2e-4] [--accum 8] [--rank 16]
Needs flash-linear-attention + triton-windows (the DeltaNet layers) in the training venv.
"""
import argparse
import json
import math
import os
import pathlib
import random
import time

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig

BASE = r"D:/BAXYRuntime/experiments/models/qwen35-4b-hf-851bf6e8"
DATA = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "comprension-2026-09-25" / "train_built"
TARGET = (r".*language_model\.layers\.\d+\..*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|"
          r"in_proj_qkv|in_proj_z|in_proj_b|in_proj_a|out_proj)$")


def encode(tok, row):
    prompt = tok.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=True,
                                     enable_thinking=False)
    p = tok(prompt, add_special_tokens=False).input_ids
    a = tok(row["answer"] + "<|im_end|>", add_special_tokens=False).input_ids
    return p, a


def loss_of(model, p, a):
    ids = torch.tensor([p + a], device="cuda")
    out = model(input_ids=ids, logits_to_keep=len(a) + 1)
    logits = out.logits[:, :-1, :].float()
    return torch.nn.functional.cross_entropy(logits.reshape(-1, logits.shape[-1]), ids[:, -len(a):].reshape(-1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--rank", type=int, default=16)
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    train = [json.loads(line) for line in open(DATA / "train.jsonl", encoding="utf-8")]
    hold = [json.loads(line) for line in open(DATA / "holdout.jsonl", encoding="utf-8")][:60]
    rng = random.Random(7)
    rng.shuffle(train)
    if args.max:
        train = train[: args.max]
    tok = AutoTokenizer.from_pretrained(BASE)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForImageTextToText.from_pretrained(BASE, quantization_config=bnb, dtype=torch.bfloat16,
                                                        device_map={"": 0})
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05,
                                             target_modules=TARGET, task_type="CAUSAL_LM"))
    params = [q for q in model.parameters() if q.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    total = math.ceil(len(train) * args.epochs / args.accum)
    warm = max(1, total // 20)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / max(1, total)))))
    log = open(out / "train.log", "a", encoding="utf-8")

    def evaluate(tag):
        model.eval()
        with torch.no_grad():
            losses = [loss_of(model, *encode(tok, row)).item() for row in hold]
        model.train()
        line = f"{time.strftime('%H:%M:%S')} {tag} holdout_loss {sum(losses) / len(losses):.4f}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    evaluate("start")
    model.train()
    steps = int(len(train) * args.epochs)
    started = time.time()
    running = []
    for i in range(steps):
        row = train[i % len(train)]
        p, a = encode(tok, row)
        loss = loss_of(model, p, a) / args.accum
        loss.backward()
        running.append(loss.item() * args.accum)
        if (i + 1) % args.accum == 0:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
        if (i + 1) % 40 == 0:
            rate = (time.time() - started) / (i + 1)
            line = (f"{time.strftime('%H:%M:%S')} ex {i + 1}/{steps} loss {sum(running[-40:]) / 40:.4f} "
                    f"lr {sched.get_last_lr()[0]:.2e} {rate:.1f}s/ex eta {(steps - i - 1) * rate / 60:.0f}min "
                    f"peak {torch.cuda.max_memory_allocated() / 2**20:.0f}MiB")
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()
        if (i + 1) % 400 == 0:
            model.save_pretrained(out / "checkpoint")
    model.save_pretrained(out)
    evaluate("end")
    (out / "TRAINING.json").write_text(json.dumps({"base": BASE, "examples": len(train), "epochs": args.epochs,
                                                   "lr": args.lr, "accum": args.accum, "rank": args.rank,
                                                   "seconds": round(time.time() - started)}), encoding="utf-8")


if __name__ == "__main__":
    main()
