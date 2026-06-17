# -*- coding: utf-8 -*-
"""A/B routing: encoder PyTorch vs ONNX int8, en procesos AISLADOS (sin contaminación torch).
Driver corre este script 2x (subproceso) y compara el top-3 de familias en una batería."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUERIES = [
    "subi el volumen a 40", "que hora es", "abri la calculadora", "gracias",
    "hola como estas", "quelle heure est-il", "what time is it", "manda un mensaje a mama",
    "buscame el clima en internet", "que es pytest", "pon musica", "aumenta el brillo",
    "conectate al wifi de casa", "quien fue einstein", "contame un chiste",
    "abra a calculadora", "que horas sao", "set the volume to 30",
    "guarda que me gusta el cafe", "sos un robot", "cuanta RAM tengo",
    "tomate una captura", "cierra spotify", "leeme los mensajes de whatsapp",
]


def worker(mode: str) -> None:
    os.environ["GEMMA4_LEAN_TOOLS"] = "0"
    os.environ["GEMMA4_ENCODER_ONNX"] = "1" if mode == "onnx" else "0"
    from gemma4_agent.routing import semantic_router as sr
    sr.embed("warmup")
    backend = type(sr._STATE.model).__name__
    top3 = {q: [f for f, _ in sr.suggest_tools_scored(q, k=3)] for q in QUERIES}
    print("##RESULT##" + json.dumps({"backend": backend, "top3": top3}))


def driver() -> int:
    out = {}
    for mode in ("torch", "onnx"):
        r = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True)
        line = next((l for l in r.stdout.splitlines() if l.startswith("##RESULT##")), None)
        if not line:
            print(f"[{mode}] sin resultado. stderr:\n{r.stderr[-800:]}")
            return 1
        out[mode] = json.loads(line[len("##RESULT##"):])
    print(f"backend torch={out['torch']['backend']}  onnx={out['onnx']['backend']}")
    t, o = out["torch"]["top3"], out["onnx"]["top3"]
    same1 = sum(t[q][0] == o[q][0] for q in QUERIES)
    same3 = sum(set(t[q]) == set(o[q]) for q in QUERIES)
    print(f"PARIDAD routing onnx vs torch: top-1 {same1}/{len(QUERIES)} | top-3 set {same3}/{len(QUERIES)}")
    for q in QUERIES:
        if t[q][0] != o[q][0]:
            print(f"  DIFF top1 {q!r}: torch={t[q]} onnx={o[q]}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("torch", "onnx"):
        worker(sys.argv[1])
    else:
        sys.exit(driver())
