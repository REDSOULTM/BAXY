"""Measures BAXY Renew's ear (Parakeet Ultra, sherpa-onnx, CPU) with and without hotwords on a synthetic set.

    <mind-runtime python> -X utf8 scripts/voice/medir_hotwords.py MANIFEST CATALOG OUT [--hoy] [--configs a,b,...]

MANIFEST: the synthetic set (a JSON list of {wav, id, voz, cond, texto, clase, nombre, acepta, lang}) that
sintetizar_frases.py writes from frases_hotwords.json, outside the repository.
CATALOG: a catalog.configure message (applicationCatalog, gameCatalog), filtered as mind.configure filters it.
--hoy: today's recognizer exactly (greedy_search, voice.py before hotwords), alone in its own process. Otherwise one
recognizer in modified_beam_search with the bpe vocab, and each configuration per stream (sherpa 1.13.4+baxy.2:
«greedy» is the per-stream greedy option, «beam» the beam without hotwords, «hwS» the beam with the hotwords at S).
Each utterance goes through voice.py's own gain. One process at a time: Ultra takes about 1 GB of RAM.

What it says: the name heard (the target name, or one of its accepted forms, in the normalized hypothesis), the WER
of all of it and of the sentences without a name, names inserted where none was said, empty or «Yeah.» results, and
the decode time per utterance (p50/p95). Synthetic voices are not the owner's: it ranks configurations, it does not
certify the product.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
import unicodedata
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind import stt_hotwords  # noqa: E402
from baxy_mind.mind import _NOT_AN_APP, _fold  # noqa: E402
from baxy_mind.speech_text import cardinal  # noqa: E402

RATE = 16000
SCORES = (1.0, 1.5, 2.0, 3.0)


def normalize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.casefold().replace("%", " por ciento").replace("+", " plus "))
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = re.sub(r"[^\w\s]|_", " ", text).split()
    return [cardinal(int(w)) if w.isdigit() and len(w) < 7 else w for w in words]


def edits(ref: list[str], hyp: list[str]) -> int:
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return row[-1]


def contains(hyp: list[str], name: list[str]) -> bool:
    joined, target = " ".join(hyp), " ".join(name)
    return bool(target) and re.search(rf"(?:^| ){re.escape(target)}(?: |$)", joined) is not None


def catalog_names(path: Path) -> list[str]:
    message = json.loads(path.read_text(encoding="utf-8"))
    apps = [str(n) for n in ((message.get("applicationCatalog") or {}).get("names") or [])
            if str(n).strip() and not _NOT_AN_APP.search(_fold(str(n)))]
    games = [str(e.get("name")) for e in ((message.get("gameCatalog") or {}).get("entries") or [])
             if isinstance(e, dict) and e.get("name")]
    return apps + games


def read(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
    peak = float(np.max(np.abs(x)))
    return x * min(8.0, 0.45 / peak) if peak >= 0.008 else x  # voice.py's _transcribe gain


def main() -> None:
    manifest, catalog, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    today = "--hoy" in sys.argv
    configs = ["hoy"] if today else ["greedy", "beam"] + [f"hw{s:g}" for s in SCORES]
    if "--configs" in sys.argv:
        configs = sys.argv[sys.argv.index("--configs") + 1].split(",")
    import sherpa_onnx

    stt = Path(os.environ["BAXY_RENEW_STT_DIR"])
    tokens = (stt / "tokens.txt").read_text(encoding="utf-8")
    forms, vocab_text = stt_hotwords.compile_hotwords(catalog_names(catalog), tokens)
    files = dict(encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
                 joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"), num_threads=4,
                 model_type="nemo_transducer", feature_dim=128, provider="cpu")
    if today:
        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(**files, decoding_method="greedy_search")
    else:
        vocab = out.with_suffix(".vocab")
        vocab.write_text(vocab_text, encoding="utf-8")
        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            **files, decoding_method="modified_beam_search", max_active_paths=4, modeling_unit="bpe",
            bpe_vocab=str(vocab))
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    audio = {r["wav"]: read(r["wav"]) for r in rows}
    hot_norm = [normalize(f) for f in forms]
    hot_norm = [h for h in hot_norm if len(" ".join(h)) >= 4]
    result: dict = {"hotwords": len(forms), "utterances": len(rows), "configs": {}}
    for config in configs:
        hot = stt_hotwords.stream_hotwords(forms, float(config[2:])) if config.startswith("hw") else None
        hyps, times = [], []
        for r in rows:
            started = time.perf_counter()
            stream = recognizer.create_stream(hot) if hot else recognizer.create_stream()
            if config == "greedy":
                stream.set_option("decoding_method", "greedy_search")
            stream.accept_waveform(RATE, audio[r["wav"]])
            recognizer.decode_stream(stream)
            times.append(time.perf_counter() - started)
            hyps.append(stream.result.text.strip())
        result["configs"][config] = summarize(rows, hyps, times, hot_norm)
        result["configs"][config]["hyps"] = hyps
        s = result["configs"][config]
        print(config, json.dumps({k: v for k, v in s.items() if k not in ("hyps", "by")}, ensure_ascii=False),
              flush=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


def summarize(rows: list[dict], hyps: list[str], times: list[float], hot_norm: list[list[str]]) -> dict:
    def block(selected: list[int]) -> dict:
        err = ref = names = named = inserted = empty = 0
        for i in selected:
            r, h = rows[i], normalize(hyps[i])
            reference = normalize(r["texto"])
            err, ref = err + edits(reference, h), ref + len(reference)
            if r.get("nombre"):
                named += 1
                accepted = [normalize(a) for a in (r.get("acepta") or [r["nombre"]])]
                names += any(contains(h, a) for a in accepted)
            elif any(contains(h, n) and not contains(reference, n) for n in hot_norm):
                inserted += 1
            empty += not h or h in (["yeah"], ["yes"])
        return {"n": len(selected), "wer": round(100 * err / max(1, ref), 2), "nombres": names, "con_nombre": named,
                "insertados": inserted, "vacios": empty}

    ordered = sorted(times)
    summary = {"todo": block(list(range(len(rows)))),
               "p50_ms": round(1000 * statistics.median(times)), "p95_ms": round(1000 * ordered[int(0.95 * len(ordered))]),
               "by": {}}
    for key in ("clase", "cond", "voz"):
        for value in sorted({r[key] for r in rows}):
            summary["by"][f"{key}={value}"] = block([i for i, r in enumerate(rows) if r[key] == value])
    return summary


if __name__ == "__main__":
    main()
