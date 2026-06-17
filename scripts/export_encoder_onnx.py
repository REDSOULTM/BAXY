# -*- coding: utf-8 -*-
"""Exporta el encoder FT (router) a ONNX int8 para el runtime sin PyTorch.

Receta reproducible del artefacto data/router_encoder_ft/model_int8.onnx, que el
semantic_router carga vía onnxruntime cuando GEMMA4_ENCODER_ONNX está activo. Motivo:
el encoder es el ÚNICO consumidor de PyTorch del runtime; cargándolo en onnxruntime int8
se suelta torch entero (~250-330 MB RAM menos, medido) + inferencia 3-5x más rápida en CPU.

VALIDADO (2026-06-17): paridad de routing top-1 19/20 vs torch (el único diff es un reorder
benigno reminder↔memory en "gracias", chitchat); tokenización tokenizers==transformers exacta;
embeddings cosine mean 0.988 vs torch (desviación típica de int8, no degrada el ranking).

Uso:  python scripts/export_encoder_onnx.py
Requiere torch + sentence-transformers (solo para EXPORTAR; el runtime no los necesita).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FT = ROOT / "gemma4_agent" / "data" / "router_encoder_ft"
OUT_FP32 = FT / "model_fp32.onnx"
OUT_INT8 = FT / "model_int8.onnx"


def main() -> int:
    import torch
    from sentence_transformers import SentenceTransformer

    m = SentenceTransformer(str(FT))
    m.eval()
    tok = m.tokenizer
    backbone = m[0].auto_model  # backbone XLM-R; pooling = mean (1_Pooling/config.json)

    class Wrap(torch.nn.Module):
        def __init__(self, b):
            super().__init__()
            self.b = b

        def forward(self, ids, mask):
            return self.b(input_ids=ids, attention_mask=mask).last_hidden_state

    w = Wrap(backbone).eval()
    enc = tok(["hola mundo"], return_tensors="pt", padding=True)
    with torch.no_grad():
        torch.onnx.export(
            w, (enc["input_ids"], enc["attention_mask"]), str(OUT_FP32),
            input_names=["input_ids", "attention_mask"], output_names=["hidden"],
            dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"},
                          "hidden": {0: "b", 1: "s"}},
            opset_version=17, dynamo=False)
    print(f"[export] fp32 -> {OUT_FP32.name} ({OUT_FP32.stat().st_size // 1_000_000} MB)")

    from onnxruntime.quantization import quantize_dynamic, QuantType
    quantize_dynamic(str(OUT_FP32), str(OUT_INT8), weight_type=QuantType.QInt8)
    print(f"[export] int8 -> {OUT_INT8.name} ({OUT_INT8.stat().st_size // 1_000_000} MB)")

    # fp32 intermedio no se necesita en runtime (el int8 es el que carga el router).
    try:
        OUT_FP32.unlink()
    except OSError:
        pass
    print("[export] listo. El runtime usa model_int8.onnx + tokenizer.json (sin torch).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
