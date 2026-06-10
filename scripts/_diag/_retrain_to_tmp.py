"""Entrena el encoder a un dir TEMPORAL (no toca router_encoder_ft/ que el
server tiene cargado) y deja todo listo para un swap atómico tras el gate.

Por qué: el asistente (gemma4_agent.server) sigue corriendo y leyó el encoder;
escribir directo sobre router_encoder_ft/ arriesga el error 1224 (sección
mapeada). Entrenamos a router_encoder_ft__new/ y router_encoder_onnx__new/;
el swap lo hace _promote_encoder.py SOLO si el gate pasa.

Uso:
    .venv_router_train/Scripts/python.exe scripts/_diag/_retrain_to_tmp.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Carga scripts/train_router_encoder.py por path (no hay scripts/__init__.py).
_spec = importlib.util.spec_from_file_location(
    "train_router_encoder", ROOT / "scripts" / "train_router_encoder.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

_FT_NEW = ROOT / "gemma4_agent" / "data" / "router_encoder_ft__new"
tr.OUT_DIR = _FT_NEW
tr.TOOL_DESC_OUT = ROOT / "gemma4_agent" / "data" / "router_encoder_ft__new_meta.json"


def _export_to_new(model_dir: Path) -> None:
    """Exporta el ONNX int8 a router_encoder_onnx__new/ (no pisa el activo)."""
    from optimum.onnxruntime import ORTModelForFeatureExtraction
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    from optimum.onnxruntime import ORTQuantizer

    onnx_dir = model_dir.parent / "router_encoder_onnx__new"
    m = ORTModelForFeatureExtraction.from_pretrained(str(model_dir), export=True)
    m.save_pretrained(str(onnx_dir))
    q = ORTQuantizer.from_pretrained(str(onnx_dir))
    qconfig = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)
    q.quantize(save_dir=str(onnx_dir), quantization_config=qconfig)
    print(f"ONNX int8 -> {onnx_dir}")


tr._export_onnx_int8 = _export_to_new

if __name__ == "__main__":
    # 2 epochs (no 3): 3 epochs derivaban la geometría global y degradaban el
    # matcher xlingual de clicks (open↔Abrir 0.85→0.62). 2 epochs reducen la
    # deriva manteniendo el fix de J Balvin. batch 64 por defecto.
    sys.argv = ["train_router_encoder.py", "--epochs", "2"]
    sys.exit(tr.main())
