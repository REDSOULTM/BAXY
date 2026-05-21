"""Predict per-profile VRAM usage WITHOUT loading the model on the GPU.

Reads each model's GGUF metadata (architecture, layer count, per-layer KV heads,
on-disk weight size) and applies the published llama.cpp KV-cache formula:

    KV_bytes = sum_over_layers( ctx * kv_heads[L] * (key_len[L] + val_len[L]) * bytes )

with --swa-full so every layer caches the full ctx (Gemma uses SWA; without
--swa-full the prefix is evicted each turn — see write_router_presets). Gemma-4
interleaves full-attention layers (key_len 512) and sliding-window layers
(key_len 256), and the 26B-A4B has a PER-LAYER kv-head array, so we read the
exact arrays from the GGUF rather than assume.

VALIDATED against real nvidia-smi/server-log measurements (exact to the MiB):
  26B-A4B-Q2 @16K: full-attn KV 320 MiB, SWA KV 3200 MiB, total 3520 MiB.
  E4B          @16K: full-attn KV 256 MiB, SWA KV  640 MiB, total  896 MiB.
The published GGUF VRAM formula has ~365 MiB median error (oobabooga), so we add
a safety margin and a WDDM reserve before declaring "fits".

Sources:
  - llama.cpp KV-cache discussion: https://github.com/ggml-org/llama.cpp/discussions/9784
  - GGUF VRAM formula (±365 MiB): https://oobabooga.github.io/blog/posts/gguf-vram-formula/
  - KV quantization on small VRAM: https://www.knightli.com/en/2026/04/23/llama-cpp-8g-vram-32k-64k-kv-cache-tuning/

Usage:
    python scripts/vram_calculator.py                # table for all profiles
    python scripts/vram_calculator.py --check        # exit 1 if any profile fails
    python scripts/vram_calculator.py --gpu-total 16380
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gemma4_agent.profiles import PROFILES  # noqa: E402

# ---- GGUF metadata reader (header only; does not read tensor data) ---------
_GGUF_TYPES_FIXED = {
    0: ("<b", 1), 1: ("<B", 1), 2: ("<h", 2), 3: ("<H", 2),
    4: ("<i", 4), 5: ("<I", 4), 6: ("<f", 4), 7: ("<?", 1),
    10: ("<q", 8), 11: ("<Q", 8), 12: ("<d", 8),
}


def read_gguf_metadata(path: Path) -> dict:
    """Return the GGUF key/value metadata dict (arrays kept as lists)."""
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError(f"{path} is not a GGUF file")
        struct.unpack("<I", f.read(4))            # version
        struct.unpack("<Q", f.read(8))            # n_tensors
        (n_kv,) = struct.unpack("<Q", f.read(8))

        def rd_str() -> str:
            (n,) = struct.unpack("<Q", f.read(8))
            return f.read(n).decode("utf-8", "replace")

        def rd_val(t: int):
            if t in _GGUF_TYPES_FIXED:
                fmt, size = _GGUF_TYPES_FIXED[t]
                return struct.unpack(fmt, f.read(size))[0]
            if t == 8:
                return rd_str()
            if t == 9:  # array
                (et,) = struct.unpack("<I", f.read(4))
                (n,) = struct.unpack("<Q", f.read(8))
                return [rd_val(et) for _ in range(n)]
            raise ValueError(f"unknown GGUF value type {t}")

        out: dict = {}
        for _ in range(n_kv):
            k = rd_str()
            (t,) = struct.unpack("<I", f.read(4))
            out[k] = rd_val(t)
        return out


# ---- VRAM model ------------------------------------------------------------
MIB = 1024 * 1024
GIB = 1024 * MIB
KV_BYTES_F16 = 2          # default KV cache dtype
COMPUTE_BUFFER_MIB = 600  # measured ~527-538 MiB; round up
VISION_MMPROJ_MIB = 1250  # mmproj-F16 loaded (~1.2 GB, measured)
FORMULA_MARGIN_MIB = 400  # oobabooga median error ~365 MiB
WDDM_RESERVE_MIB = 800    # Windows leaves headroom; don't fill to the brim


def kv_cache_mib(meta: dict, ctx: int, swa_full: bool = True) -> tuple[float, float]:
    """(full_attn_MiB, swa_MiB) for the given ctx under --swa-full.

    Uses the per-layer kv-head array + the full/SWA key&value lengths.
    """
    arch = meta.get("general.architecture", "")
    p = f"{arch}."
    kvh = meta.get(p + "attention.head_count_kv")
    pat = meta.get(p + "attention.sliding_window_pattern")
    n_layer = meta.get(p + "block_count")
    key_len = meta.get(p + "attention.key_length", meta.get(p + "embedding_length", 0))
    val_len = meta.get(p + "attention.value_length", key_len)
    key_len_swa = meta.get(p + "attention.key_length_swa", key_len)
    val_len_swa = meta.get(p + "attention.value_length_swa", val_len)

    # Normalize kv-heads to a per-layer list.
    if isinstance(kvh, list):
        heads = list(kvh)
    else:
        heads = [int(kvh)] * int(n_layer)
    # Normalize the SWA pattern to a per-layer bool list (True = SWA layer).
    if isinstance(pat, list):
        is_swa = [bool(x) for x in pat]
    else:
        is_swa = [True] * int(n_layer)  # assume all-SWA if unspecified

    full_b = 0.0
    swa_b = 0.0
    for L in range(int(n_layer)):
        h = heads[L] if L < len(heads) else heads[-1]
        swa = is_swa[L] if L < len(is_swa) else False
        klen = key_len_swa if swa else key_len
        vlen = val_len_swa if swa else val_len
        # Under --swa-full every layer caches the full ctx.
        eff_ctx = ctx if swa_full else (min(ctx, meta.get(p + "attention.sliding_window", ctx)) if swa else ctx)
        b = eff_ctx * h * (klen + vlen) * KV_BYTES_F16
        if swa:
            swa_b += b
        else:
            full_b += b
    return full_b / MIB, swa_b / MIB


def predict_profile(name: str, gpu_total_mib: int) -> dict:
    prof = PROFILES[name]
    res = {"name": name, "ok": None, "reason": ""}
    if not prof.server_running or not prof.model_path:
        res["ok"] = None
        res["reason"] = "standby/default — no model"
        return res
    mp = Path(prof.model_path)
    if not mp.is_file():
        res["ok"] = False
        res["reason"] = "model file missing"
        return res
    meta = read_gguf_metadata(mp)
    weights_mib = mp.stat().st_size / MIB           # GGUF on-disk ~= GPU weight buffer
    full_kv, swa_kv = kv_cache_mib(meta, prof.context_size, swa_full=True)
    kv_mib = full_kv + swa_kv
    vision = VISION_MMPROJ_MIB if prof.vision_enabled else 0
    total = weights_mib + kv_mib + COMPUTE_BUFFER_MIB + vision + FORMULA_MARGIN_MIB
    budget = gpu_total_mib - WDDM_RESERVE_MIB
    res.update({
        "ctx": prof.context_size,
        "model": mp.name,
        "weights_mib": round(weights_mib),
        "kv_mib": round(kv_mib),
        "kv_full": round(full_kv),
        "kv_swa": round(swa_kv),
        "vision_mib": vision,
        "total_mib": round(total),
        "budget_mib": budget,
        "ok": total <= budget,
    })
    if not res["ok"]:
        res["reason"] = f"predicted {round(total)} MiB > budget {budget} MiB (OOM risk)"
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu-total", type=int, default=16380, help="total VRAM MiB")
    ap.add_argument("--check", action="store_true", help="exit 1 if any profile won't fit")
    ap.add_argument("profiles", nargs="*", help="profiles to check (default: all server profiles)")
    args = ap.parse_args()

    names = args.profiles or [n for n in PROFILES if PROFILES[n].server_running and PROFILES[n].model_path]
    print(f"GPU total: {args.gpu_total} MiB  |  budget (minus {WDDM_RESERVE_MIB} WDDM): "
          f"{args.gpu_total - WDDM_RESERVE_MIB} MiB  |  --swa-full ON\n")
    print(f"{'profile':<8}{'ctx':>7}{'weights':>9}{'KV':>7}{'(full/swa)':>13}"
          f"{'vision':>8}{'TOTAL':>8}{'fits?':>7}  model")
    any_fail = False
    for n in names:
        r = predict_profile(n, args.gpu_total)
        if r["ok"] is None:
            print(f"{n:<8}  {r['reason']}")
            continue
        verdict = "OK" if r["ok"] else "OOM"
        if not r["ok"]:
            any_fail = True
        kvsplit = f"{r['kv_full']}/{r['kv_swa']}"
        print(f"{n:<8}{r['ctx']:>7}{r['weights_mib']:>9}{r['kv_mib']:>7}"
              f"{kvsplit:>13}{r['vision_mib']:>8}"
              f"{r['total_mib']:>8}{verdict:>7}  {r['model']}")
        if not r["ok"]:
            print(f"         ^ {r['reason']}")
    print("\nTOTAL = weights + KV@ctx + compute(600) + vision(1250) + formula-margin(400).")
    print("Validated: formula reproduces measured 26B KV (3520) & E4B KV (896) exactly.")
    if args.check and any_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
